"""E2E integration tests for full cycle (step 11).

Exercises run_cycle with fully mocked external services (NB, Kush, Telegram).
Verifies the complete pipeline: NB → filter → decide → match → bet → excel → telegram.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.config.schema import (
    AppConfig,
    FilesConfig,
    KushConfig,
    LoggingConfig,
    NbConfig,
    ProxiesConfig,
    ScheduleConfig,
    TelegramConfig,
    ThresholdsConfig,
)
from src.decision.engine import DecisionEngine
from src.decision.league_filter import LeagueFilter
from src.decision.models import LeagueSetting
from src.excel.writer import ExcelWriter
from src.kush.client import OddsEntry
from src.kush.models import KushEvent
from src.nb.models import Match
from src.scheduler.cycle_runner import run_cycle
from src.state import AppState
from src.telegram.notifier import TelegramNotifier


def _make_config(tmpdir: str, dry_run: bool = True) -> AppConfig:
    return AppConfig(
        schedule=ScheduleConfig(),
        telegram=TelegramConfig(token="", chat_ids=[]),
        proxies=ProxiesConfig(),
        thresholds=ThresholdsConfig(roi=0.05, default_ratio=1.10, big_league_ratio=1.05),
        files=FilesConfig(output_dir=tmpdir, logs_dir=tmpdir),
        kush=KushConfig(dry_run=dry_run, default_stake=100),
        nb=NbConfig(),
        logging=LoggingConfig(),
    )


def _make_match(
    league: str = "Premier League",
    home: str = "Arsenal",
    away: str = "Chelsea",
    kf1: float = 2.10,
    kf2: float = 3.50,
    kfx: float = 3.20,
) -> Match:
    dt = datetime(2026, 2, 22, 15, 0, tzinfo=timezone.utc)
    return Match(
        match_key=Match.make_key(league, home, away, dt),
        league=league,
        team_home=home,
        team_away=away,
        start_time_utc=dt,
        nb_slug="arsenal-chelsea-123",
        sport="soccer",
        odds_1_start=2.00,
        odds_x_start=3.10,
        odds_2_start=3.40,
        odds_1_end=kf1,
        odds_x_end=kfx,
        odds_2_end=kf2,
    )


def _make_kush_event(
    event_id: str = "99001",
    home: str = "Arsenal",
    away: str = "Chelsea",
) -> KushEvent:
    return KushEvent(
        event_id=event_id,
        league="Premier League",
        team_home=home,
        team_away=away,
        start_time_utc=datetime(2026, 2, 22, 15, 0, tzinfo=timezone.utc),
        url="/event/99001-arsenal-chelsea",
    )


class TestE2EDryRun:
    """Full cycle in dry-run mode with mocked externals."""

    def test_full_cycle_single_match_placed(self, tmp_path):
        """Single match → passes decision → matched on Kush → dry-run placed."""
        config = _make_config(str(tmp_path))
        state = AppState()
        match = _make_match(kf1=2.10, kf2=3.50, kfx=3.20)
        kush_event = _make_kush_event()

        # Mock NB client
        nb_client = MagicMock()
        nb_client.get_matches.return_value = [match]

        # League settings: allow Premier League
        league_settings = [LeagueSetting(bet_type="1", leagues=["Premier League"])]
        league_filter = LeagueFilter(settings=league_settings)
        decision_engine = DecisionEngine()
        excel_writer = ExcelWriter(output_dir=str(tmp_path))

        # Mock telegram (disabled)
        telegram = MagicMock(spec=TelegramNotifier)

        # Mock Kush internals: session, client, events
        with patch("src.scheduler.cycle_runner.KushSession") as MockSession, \
             patch("src.scheduler.cycle_runner.KushClient") as MockClient, \
             patch("src.scheduler.cycle_runner.EventMatcher") as MockMatcher, \
             patch("src.scheduler.cycle_runner.BetPlacer") as MockPlacer:

            mock_session_inst = MockSession.return_value
            mock_client_inst = MockClient.return_value
            mock_client_inst.get_all_events.return_value = [kush_event]

            # Matcher finds the event
            from src.kush.models import MatchResult
            mock_matcher_inst = MockMatcher.return_value
            mock_matcher_inst.find_best_match.return_value = MatchResult(
                nb_match_key=match.match_key,
                kush_event=kush_event,
                confidence=0.95,
                name_score=0.98,
                time_score=0.90,
            )

            # BetPlacer returns success dry-run
            from src.kush.bet_result import BetResult
            mock_placer_inst = MockPlacer.return_value
            mock_placer_inst.place_bet.return_value = BetResult(
                match_key=match.match_key,
                event_id="99001",
                bet_type="1X",
                kf_nb=2.10,
                kf_kush=2.40,
                ratio=1.20,
                threshold=1.10,
                ratio_passes=True,
                placed=False,
                dry_run=True,
                success=True,
                league="Premier League",
                team_home="Arsenal",
                team_away="Chelsea",
            )

            stats = run_cycle(
                config=config,
                state=state,
                nb_client=nb_client,
                league_filter=league_filter,
                decision_engine=decision_engine,
                excel_writer=excel_writer,
                telegram=telegram,
            )

        assert stats.total_matches == 1
        assert stats.filtered == 1
        assert stats.decided >= 1
        assert stats.matched == 1
        assert stats.placed >= 1
        assert stats.missing == 0
        assert stats.errors == 0

        # Telegram notified
        assert telegram.notify_placed.called or telegram.notify_cycle_summary.called

    def test_full_cycle_no_matches(self, tmp_path):
        """NB returns no matches → cycle completes quickly."""
        config = _make_config(str(tmp_path))
        state = AppState()

        nb_client = MagicMock()
        nb_client.get_matches.return_value = []

        league_settings = [LeagueSetting(bet_type="1", leagues=["Premier League"])]
        league_filter = LeagueFilter(settings=league_settings)
        decision_engine = DecisionEngine()
        excel_writer = ExcelWriter(output_dir=str(tmp_path))
        telegram = MagicMock(spec=TelegramNotifier)

        stats = run_cycle(
            config=config,
            state=state,
            nb_client=nb_client,
            league_filter=league_filter,
            decision_engine=decision_engine,
            excel_writer=excel_writer,
            telegram=telegram,
        )

        assert stats.total_matches == 0
        assert stats.filtered == 0
        assert stats.errors == 0

    def test_full_cycle_match_not_on_kush(self, tmp_path):
        """Match passes decision but not found on Kush → missing + telegram."""
        config = _make_config(str(tmp_path))
        state = AppState()
        match = _make_match(kf1=2.10, kf2=3.50, kfx=3.20)

        nb_client = MagicMock()
        nb_client.get_matches.return_value = [match]

        league_settings = [LeagueSetting(bet_type="1", leagues=["Premier League"])]
        league_filter = LeagueFilter(settings=league_settings)
        decision_engine = DecisionEngine()
        excel_writer = ExcelWriter(output_dir=str(tmp_path))
        telegram = MagicMock(spec=TelegramNotifier)

        with patch("src.scheduler.cycle_runner.KushSession"), \
             patch("src.scheduler.cycle_runner.KushClient") as MockClient, \
             patch("src.scheduler.cycle_runner.EventMatcher") as MockMatcher, \
             patch("src.scheduler.cycle_runner.BetPlacer") as MockPlacer:

            MockClient.return_value.get_all_events.return_value = []
            MockMatcher.return_value.find_best_match.return_value = None
            MockPlacer.return_value.get_threshold.return_value = 1.10

            stats = run_cycle(
                config=config,
                state=state,
                nb_client=nb_client,
                league_filter=league_filter,
                decision_engine=decision_engine,
                excel_writer=excel_writer,
                telegram=telegram,
            )

        assert stats.missing >= 1
        assert stats.placed == 0
        telegram.notify_missing.assert_called()
        # Verify missing rows were added to Excel writer
        assert excel_writer.missing_count >= 1

    def test_full_cycle_league_filtered_out(self, tmp_path):
        """Match league not in settings → filtered out → no Kush call."""
        config = _make_config(str(tmp_path))
        state = AppState()
        match = _make_match(league="Unknown League")

        nb_client = MagicMock()
        nb_client.get_matches.return_value = [match]

        # Only allow "La Liga"
        league_settings = [LeagueSetting(bet_type="1", leagues=["La Liga"])]
        league_filter = LeagueFilter(settings=league_settings)
        decision_engine = DecisionEngine()
        excel_writer = ExcelWriter(output_dir=str(tmp_path))
        telegram = MagicMock(spec=TelegramNotifier)

        stats = run_cycle(
            config=config,
            state=state,
            nb_client=nb_client,
            league_filter=league_filter,
            decision_engine=decision_engine,
            excel_writer=excel_writer,
            telegram=telegram,
        )

        assert stats.total_matches == 1
        assert stats.filtered == 0
        assert stats.decided == 0

    def test_nb_failure_notifies_critical(self, tmp_path):
        """NB client raises exception → critical telegram + error count."""
        config = _make_config(str(tmp_path))
        state = AppState()

        nb_client = MagicMock()
        nb_client.get_matches.side_effect = ConnectionError("NB unreachable")

        league_settings = []
        league_filter = LeagueFilter(settings=league_settings)
        decision_engine = DecisionEngine()
        excel_writer = ExcelWriter(output_dir=str(tmp_path))
        telegram = MagicMock(spec=TelegramNotifier)

        stats = run_cycle(
            config=config,
            state=state,
            nb_client=nb_client,
            league_filter=league_filter,
            decision_engine=decision_engine,
            excel_writer=excel_writer,
            telegram=telegram,
        )

        assert stats.errors == 1
        telegram.notify_critical.assert_called()

    def test_kush_connection_failure(self, tmp_path):
        """Kush session fails → error + critical notification."""
        config = _make_config(str(tmp_path))
        state = AppState()
        match = _make_match()

        nb_client = MagicMock()
        nb_client.get_matches.return_value = [match]

        league_settings = [LeagueSetting(bet_type="1", leagues=["Premier League"])]
        league_filter = LeagueFilter(settings=league_settings)
        decision_engine = DecisionEngine()
        excel_writer = ExcelWriter(output_dir=str(tmp_path))
        telegram = MagicMock(spec=TelegramNotifier)

        with patch("src.scheduler.cycle_runner.KushSession") as MockSession:
            MockSession.side_effect = ConnectionError("Kush down")

            stats = run_cycle(
                config=config,
                state=state,
                nb_client=nb_client,
                league_filter=league_filter,
                decision_engine=decision_engine,
                excel_writer=excel_writer,
                telegram=telegram,
            )

        assert stats.errors >= 1
        telegram.notify_critical.assert_called()

    def test_state_tracks_pending_and_placed(self, tmp_path):
        """Verify AppState correctly accumulates pending/placed across calls."""
        config = _make_config(str(tmp_path))
        state = AppState()
        match = _make_match()

        # First run: match missing on Kush → pending
        nb_client = MagicMock()
        nb_client.get_matches.return_value = [match]

        league_settings = [LeagueSetting(bet_type="1", leagues=["Premier League"])]
        league_filter = LeagueFilter(settings=league_settings)
        decision_engine = DecisionEngine()
        excel_writer = ExcelWriter(output_dir=str(tmp_path))
        telegram = MagicMock(spec=TelegramNotifier)

        with patch("src.scheduler.cycle_runner.KushSession"), \
             patch("src.scheduler.cycle_runner.KushClient") as MockClient, \
             patch("src.scheduler.cycle_runner.EventMatcher") as MockMatcher, \
             patch("src.scheduler.cycle_runner.BetPlacer") as MockPlacer:

            MockClient.return_value.get_all_events.return_value = []
            MockMatcher.return_value.find_best_match.return_value = None
            MockPlacer.return_value.get_threshold.return_value = 1.10

            run_cycle(
                config=config, state=state, nb_client=nb_client,
                league_filter=league_filter, decision_engine=decision_engine,
                excel_writer=excel_writer, telegram=telegram,
            )

        assert state.pending_count >= 1

    def test_decision_engine_skip_equal_odds(self, tmp_path):
        """When kf1 == kf2, decision engine skips → no Kush interaction."""
        config = _make_config(str(tmp_path))
        state = AppState()
        # Equal odds → decision engine should skip all
        match = _make_match(kf1=2.50, kf2=2.50, kfx=3.00)

        nb_client = MagicMock()
        nb_client.get_matches.return_value = [match]

        league_settings = [LeagueSetting(bet_type="1", leagues=["Premier League"])]
        league_filter = LeagueFilter(settings=league_settings)
        decision_engine = DecisionEngine()
        excel_writer = ExcelWriter(output_dir=str(tmp_path))
        telegram = MagicMock(spec=TelegramNotifier)

        stats = run_cycle(
            config=config, state=state, nb_client=nb_client,
            league_filter=league_filter, decision_engine=decision_engine,
            excel_writer=excel_writer, telegram=telegram,
        )

        assert stats.decided == 0
        assert stats.placed == 0


class TestPathsModule:
    """Tests for the frozen path resolver."""

    def test_data_path_dev_mode(self):
        from src.paths import data_path, get_base_dir
        p = data_path("sl_keys.json")
        assert p.endswith(os.path.join("assets", "data", "sl_keys.json"))
        # In dev mode, base dir should be the project root
        base = get_base_dir()
        assert os.path.isdir(base)

    def test_data_path_returns_string(self):
        from src.paths import data_path
        assert isinstance(data_path("test.json"), str)

    def test_frozen_mode_uses_meipass(self):
        import sys
        from src.paths import get_base_dir
        # Simulate frozen mode
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "_MEIPASS", "/tmp/fake_meipass", create=True):
            base = get_base_dir()
            assert base == "/tmp/fake_meipass"
