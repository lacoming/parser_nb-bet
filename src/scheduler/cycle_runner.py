"""Full cycle orchestration.

One cycle: NB-Bet -> filter -> decide -> Kush match -> bet -> excel -> telegram.
"""
from __future__ import annotations

import logging
from typing import Optional

from src.config.schema import AppConfig
from src.decision.engine import DecisionEngine
from src.decision.league_filter import LeagueFilter
from src.excel.models import ExcelRow
from src.excel.writer import ExcelWriter
from src.kush.bet_placer import BetPlacer
from src.kush.client import KushClient
from src.kush.matcher import EventMatcher
from src.kush.session import KushSession
from src.nb.client import NbClient
from src.nb.models import Match
from src.state import AppState
from src.telegram.notifier import TelegramNotifier

log = logging.getLogger(__name__)


class CycleStats:
    """Tracks statistics for one cycle run."""

    def __init__(self) -> None:
        self.total_matches = 0
        self.filtered = 0
        self.decided = 0
        self.matched = 0
        self.placed = 0
        self.missing = 0
        self.errors = 0


def _match_to_excel_row(match: Match) -> ExcelRow:
    """Convert a Match to an ExcelRow with basic info."""
    return ExcelRow(
        date=match.start_time_utc.strftime("%d.%m.%Y"),
        time=match.start_time_utc.strftime("%H:%M"),
        league=match.league,
        team_home=match.team_home,
        team_away=match.team_away,
        odds_1_start=f"{match.odds_1_start:.2f}" if match.odds_1_start else "",
        odds_1_end=f"{match.odds_1_end:.2f}" if match.odds_1_end else "",
        odds_x_start=f"{match.odds_x_start:.2f}" if match.odds_x_start else "",
        odds_x_end=f"{match.odds_x_end:.2f}" if match.odds_x_end else "",
        odds_2_start=f"{match.odds_2_start:.2f}" if match.odds_2_start else "",
        odds_2_end=f"{match.odds_2_end:.2f}" if match.odds_2_end else "",
        link=match.nb_slug,
    )


def run_cycle(
    config: AppConfig,
    state: AppState,
    nb_client: NbClient,
    league_filter: LeagueFilter,
    decision_engine: DecisionEngine,
    excel_writer: ExcelWriter,
    telegram: TelegramNotifier,
    proxies: Optional[list[str]] = None,
) -> CycleStats:
    """Execute one full cycle.

    Returns CycleStats with counts.
    """
    stats = CycleStats()

    # 1. Fetch matches from NB-Bet
    log.info("Fetching NB-Bet matches...")
    try:
        matches = nb_client.get_matches(
            sport="soccer",
            window_days=config.schedule.window_days,
        )
        stats.total_matches = len(matches)
        log.info("Fetched %d matches from NB-Bet", stats.total_matches)
    except Exception:
        log.exception("Failed to fetch NB-Bet matches")
        stats.errors += 1
        telegram.notify_critical("Failed to fetch NB-Bet matches")
        return stats

    # 2. Filter by leagues
    filtered = league_filter.filter(matches)
    stats.filtered = len(filtered)
    log.info("League filter: %d -> %d matches", stats.total_matches, stats.filtered)

    # 3. Decision engine
    passing = []
    for match in filtered:
        decisions = decision_engine.get_passing_decisions(match)
        if decisions:
            # Find the league setting to get per-league ROI
            setting = league_filter.find_setting(match)
            league_roi = setting.roi if setting else 0.0
            passing.append((match, decisions, league_roi))
    stats.decided = len(passing)
    log.info("Decision engine: %d matches with passing bets", stats.decided)

    if not passing:
        log.info("No passing decisions, cycle complete")
        telegram.notify_cycle_summary(
            total_matches=stats.total_matches,
            filtered=stats.filtered,
            decided=0,
            matched=0,
            placed=0,
            missing=0,
            errors=stats.errors,
            dry_run=config.kush.dry_run,
        )
        return stats

    # 4. Kush session and matching
    try:
        kush_session = KushSession(
            base_url=config.kush.base_url,
            proxy=proxies[0] if proxies else None,
        )
        kush_session.init_csrf()
        kush_client = KushClient(kush_session)
        all_events = kush_client.get_all_events()
        log.info("Fetched %d Kush events", len(all_events))
    except Exception:
        log.exception("Failed to connect to Kush")
        stats.errors += 1
        telegram.notify_critical("Failed to connect to Kush")
        return stats

    matcher = EventMatcher(
        time_tolerance_hours=config.kush.match_time_tolerance_hours,
        min_confidence=config.kush.min_confidence,
    )

    bet_placer = BetPlacer(
        session=kush_session,
        client=kush_client,
        thresholds=config.thresholds,
        kush_config=config.kush,
    )

    # 5. Match and place bets
    for match, decisions, league_roi in passing:
        kush_league = league_filter.get_kush_league(match.league)
        result = matcher.find_best_match(match, all_events, kush_league_name=kush_league)

        if result is None:
            stats.missing += 1
            if state.enqueue_pending(match.match_key, [d.bet_type for d in decisions]):
                telegram.notify_missing(
                    match_key=match.match_key,
                    league=match.league,
                    team_home=match.team_home,
                    team_away=match.team_away,
                )
            continue

        stats.matched += 1
        kush_event = result.kush_event

        for decision in decisions:
            try:
                # Determine which NB odds to use for ratio
                kf_nb = _get_kf_nb(match, decision.bet_type)
                if kf_nb is None or kf_nb <= 0:
                    log.warning("No NB odds for %s on %s", decision.bet_type, match.match_key)
                    continue

                bet_result = bet_placer.place_bet(
                    match=match,
                    kush_event_id=kush_event.event_id,
                    kush_event_url=kush_event.url,
                    bet_type_kush=decision.bet_type,
                    kf_nb=kf_nb,
                    dry_run=config.kush.dry_run,
                    roi=league_roi,
                )
                if bet_result.success:
                    stats.placed += 1
                    state.record_placed(match.match_key)

                    row = _match_to_excel_row(match)
                    row.bet_type = bet_result.bet_type
                    row.kf_kush = f"{bet_result.kf_kush:.2f}"
                    row.ratio = f"{bet_result.ratio:.3f}"
                    excel_writer.add_row(row)

                    telegram.notify_placed(
                        match_key=match.match_key,
                        bet_type=bet_result.bet_type,
                        kf_nb=bet_result.kf_nb,
                        kf_kush=bet_result.kf_kush,
                        ratio=bet_result.ratio,
                        threshold=bet_result.threshold,
                        dry_run=bet_result.dry_run,
                        league=match.league,
                        team_home=match.team_home,
                        team_away=match.team_away,
                    )
                else:
                    log.warning("Bet failed: %s", bet_result.summary)
            except Exception:
                log.exception("Error placing bet for %s", match.match_key)
                stats.errors += 1

    # 6. Save Excel
    if excel_writer.row_count > 0:
        try:
            path = excel_writer.save()
            telegram.send_document(path, caption="Результаты цикла")
        except Exception:
            log.exception("Failed to save Excel")
            stats.errors += 1

    # 7. Cycle summary
    telegram.notify_cycle_summary(
        total_matches=stats.total_matches,
        filtered=stats.filtered,
        decided=stats.decided,
        matched=stats.matched,
        placed=stats.placed,
        missing=stats.missing,
        errors=stats.errors,
        dry_run=config.kush.dry_run,
    )

    log.info(
        "Cycle done: %d total, %d filtered, %d decided, %d matched, %d placed, %d missing, %d errors",
        stats.total_matches,
        stats.filtered,
        stats.decided,
        stats.matched,
        stats.placed,
        stats.missing,
        stats.errors,
    )

    return stats


def _get_kf_nb(match: Match, bet_type: str) -> Optional[float]:
    """Extract the appropriate NB coefficient for a given bet type."""
    bt = bet_type.upper()
    if bt in ("1", "П1"):
        return match.odds_1_end
    elif bt in ("2", "П2"):
        return match.odds_2_end
    elif bt in ("X", "НИЧЬЯ"):
        return match.odds_x_end
    elif bt in ("1X",):
        return match.odds_1x_end
    return match.odds_1_end  # fallback
