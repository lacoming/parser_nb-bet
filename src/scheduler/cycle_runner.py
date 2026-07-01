"""Full cycle orchestration.

One cycle: NB-Bet -> filter -> decide -> Kush match -> bet -> excel -> telegram.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.config.schema import AppConfig
from src.decision.league_filter import LeagueFilter
from src.decision.models import BetDecision
from src.excel.models import UnifiedRow
from src.excel.writer import ExcelWriter
from src.kush.bet_placer import BetPlacer
from src.kush.client import KushClient
from src.kush.matcher import EventMatcher, NearMissTracker
from src.kush.session import KushSession
from src.nb.bet_placer import NbBetPlacer
from src.nb.client import NbClient
from src.nb.models import Match
from src.nb.session import NbSession
from src.state import AppState
from src.vk.notifier import VkNotifier

log = logging.getLogger("parser_nb_bet.scheduler.cycle_runner")


def _resolve_writable_data_path(filename: str) -> str:
    """Resolve path to a writable file in assets/data/ (next to exe, not inside)."""
    from src.paths import writable_data_path
    return writable_data_path(filename)


# Decision engine bet types -> Kush bet types
_DECISION_TO_KUSH: dict[str, str] = {
    "1": "П1",
    "2": "П2",
    "X": "X",
}


def _to_kush_bet_type(bet_type: str) -> str:
    """Translate decision engine bet type to Kush format."""
    return _DECISION_TO_KUSH.get(bet_type, bet_type)


class CycleStats:
    """Tracks statistics for one cycle run."""

    def __init__(self) -> None:
        self.total_matches = 0
        self.filtered = 0
        self.decided = 0
        self.matched = 0
        self.placed = 0
        self.missing = 0
        self.rejected = 0
        self.pending = 0
        self.nb_placed = 0
        self.errors = 0


def _get_default_threshold(config: AppConfig, league: str) -> float:
    """Return ratio threshold for a league (big or default), without BetPlacer."""
    for big in config.thresholds.big_leagues:
        if big.lower() in league.lower():
            return config.thresholds.big_league_ratio
    return config.thresholds.default_ratio


def _fmt(val: Optional[float], fmt: str = ":.2f") -> str:
    """Format a float or return empty string."""
    if val is None or val <= 0:
        return ""
    return f"{val:.2f}"


def run_cycle(
    config: AppConfig,
    state: AppState,
    nb_client: NbClient,
    league_filter: LeagueFilter,
    excel_writer: ExcelWriter,
    telegram: VkNotifier,
    proxies: Optional[list[str]] = None,
    tracker: Optional[NearMissTracker] = None,
) -> CycleStats:
    """Execute one full cycle.

    Returns CycleStats with counts.
    """
    stats = CycleStats()

    # Import confirmed near-misses into aliases at cycle start
    if tracker:
        imported = tracker.import_confirmed()
        if imported:
            from src.kush.normalizer import load_aliases
            aliases_path = _resolve_writable_data_path("sl_teams_zamen.json")
            load_aliases(aliases_path)

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
        return stats

    # 2. Filter by leagues
    filtered = league_filter.filter(matches)
    stats.filtered = len(filtered)
    log.info("League filter: %d -> %d matches", stats.total_matches, stats.filtered)

    # 2b. Split near-window vs far-future (Kush serves day 0/1/2)
    _MSK_OFFSET = timedelta(hours=3)
    now_msk = datetime.now(timezone.utc) + _MSK_OFFSET
    kush_max_date = now_msk.replace(
        hour=23, minute=59, second=59, microsecond=0,
    ) + timedelta(days=2)
    near_matches = [m for m in filtered if m.start_time_utc <= kush_max_date]
    far_matches = [m for m in filtered if m.start_time_utc > kush_max_date]
    if far_matches:
        log.info(
            "%d matches beyond Kush window (after %s MSK) -> pending",
            len(far_matches),
            kush_max_date.strftime("%d.%m %H:%M"),
        )

    # 2b-2. Process far-future matches through decision engine -> pending rows + TG
    # Also collect far-decided for NB placement (B1 fix)
    far_decided: list[tuple[Match, str, float]] = []  # (match, bet_type, roi)
    for far_match in far_matches:
        setting = league_filter.find_setting(far_match)
        if not setting:
            continue
        if not setting.check(far_match.odds_1_start, far_match.odds_2_start):
            if far_match.odds_1_start is None or far_match.odds_2_start is None:
                reason = "нет кф старт"
                log.warning(
                    "Skipping %s: missing start odds (kf1=%s, kf2=%s)",
                    far_match.match_key, far_match.odds_1_start, far_match.odds_2_start,
                )
            else:
                reason = "условие"
                log.debug(
                    "Conditions not met for far %s bet=%s: kf1=%s kf2=%s",
                    far_match.match_key, setting.bet_type,
                    far_match.odds_1_start, far_match.odds_2_start,
                )
            excel_writer.add_row(UnifiedRow(
                date=far_match.start_time_utc.strftime("%d.%m.%Y"),
                time=far_match.start_time_utc.strftime("%H:%M"),
                league=far_match.league,
                team_home=far_match.team_home,
                team_away=far_match.team_away,
                bet_type=setting.bet_type,
                kf1_start=_fmt(far_match.odds_1_start),
                kfx_start=_fmt(far_match.odds_x_start),
                kf2_start=_fmt(far_match.odds_2_start),
                kf_nb="",
                min_kf_kush="",
                nb_placed="-",
                kush_placed="-",
                kush_reason=reason,
                kf_kush="",
                kush_date="",
                kush_time="",
                link=far_match.nb_url,
            ))
            continue
        target_bet_type = setting.bet_type
        league_roi = setting.roi
        kf_nb = _get_kf_nb(far_match, target_bet_type)
        threshold = _get_default_threshold(config, far_match.league)
        effective_roi = league_roi if league_roi else config.thresholds.roi
        min_kf = (threshold * kf_nb / (1 + effective_roi)) if kf_nb and kf_nb > 0 else 0.0

        far_decided.append((far_match, target_bet_type, league_roi))

        excel_writer.add_row(UnifiedRow(
            date=far_match.start_time_utc.strftime("%d.%m.%Y"),
            time=far_match.start_time_utc.strftime("%H:%M"),
            league=far_match.league,
            team_home=far_match.team_home,
            team_away=far_match.team_away,
            bet_type=target_bet_type,
            kf1_start=_fmt(far_match.odds_1_start),
            kfx_start=_fmt(far_match.odds_x_start),
            kf2_start=_fmt(far_match.odds_2_start),
            kf_nb=_fmt(kf_nb),
            min_kf_kush=_fmt(min_kf),
            nb_placed="",  # will be filled after NB placement pass
            kush_placed="-",
            kush_reason="ожидание",
            kf_kush="",
            kush_date="",
            kush_time="",
            link=far_match.nb_url,
        ))
        stats.pending += 1

        # TG notification only for newly seen far-future matches (dedup across cycles)
        if state.record_far_pending(far_match.match_key):
            telegram.notify_pending(
                match_key=far_match.match_key,
                league=far_match.league,
                team_home=far_match.team_home,
                team_away=far_match.team_away,
                match_time=far_match.start_time_utc.strftime("%H:%M"),
                match_date=far_match.start_time_utc.strftime("%d.%m.%Y"),
                bet_type=target_bet_type,
                odds_1=_fmt(far_match.odds_1_start),
                odds_x=_fmt(far_match.odds_x_start),
                odds_2=_fmt(far_match.odds_2_start),
                link=far_match.nb_url,
            )

    # 2c. Skip already-processed matches
    new_matches = [m for m in near_matches if not state.is_processed(m.match_key)]
    skipped = len(filtered) - len(new_matches) - len(far_matches)
    if skipped > 0:
        log.info("Skipped %d already-processed matches", skipped)

    # 3. Decision engine — one bet type per match from leagues.xlsx
    passing: list[tuple[Match, BetDecision, float]] = []
    for match in new_matches:
        setting = league_filter.find_setting(match)
        if not setting:
            log.debug("No league setting for %s", match.match_key)
            continue
        league_roi = setting.roi
        target_bet_type = setting.bet_type
        if not setting.check(match.odds_1_start, match.odds_2_start):
            if match.odds_1_start is None or match.odds_2_start is None:
                reason = "нет кф старт"
                log.warning(
                    "Skipping %s: missing start odds (kf1=%s, kf2=%s)",
                    match.match_key, match.odds_1_start, match.odds_2_start,
                )
            else:
                reason = "условие"
                log.debug(
                    "Conditions not met for %s bet=%s: kf1_start=%s kf2_start=%s",
                    match.match_key, target_bet_type, match.odds_1_start, match.odds_2_start,
                )
            excel_writer.add_row(UnifiedRow(
                date=match.start_time_utc.strftime("%d.%m.%Y"),
                time=match.start_time_utc.strftime("%H:%M"),
                league=match.league,
                team_home=match.team_home,
                team_away=match.team_away,
                bet_type=target_bet_type,
                kf1_start=_fmt(match.odds_1_start),
                kfx_start=_fmt(match.odds_x_start),
                kf2_start=_fmt(match.odds_2_start),
                kf_nb="",
                min_kf_kush="",
                nb_placed="-",
                kush_placed="-",
                kush_reason=reason,
                kf_kush="",
                kush_date="",
                kush_time="",
                link=match.nb_url,
            ))
            continue
        decision = BetDecision(
            bet_type=target_bet_type,
            passes=True,
            reasons=[f"league: {setting.condition_raw}"],
        )
        passing.append((match, decision, league_roi))
    stats.decided = len(passing)
    log.info("Decision engine: %d matches with passing bets", stats.decided)

    # 3b. NB-Bet tip placement — for ALL decided matches (near + far) [B1 fix]
    nb_placer = None
    if config.nb.login and config.nb.password:
        try:
            nb_session = NbSession(
                proxy=proxies[0] if proxies else None,
                timeout=config.nb.timeout_seconds,
                retries=config.nb.retries,
                retry_delay=float(config.nb.retry_delay_seconds),
            )
            nb_session.login(config.nb.login, config.nb.password)
            nb_placer = NbBetPlacer(nb_session, config.nb)
        except Exception:
            log.exception("NB-Bet login failed")
            stats.errors += 1

    nb_funds_exhausted = False
    if nb_placer:
        # Near-window decided matches
        for match, decision, _lr in passing:
            if state.is_nb_placed(match.match_key):
                continue
            nb_result = nb_placer.place_tip(
                match, decision.bet_type, config.nb.dry_run,
            )
            if nb_result.insufficient_funds:
                log.warning("NB insufficient funds — stopping NB bets this cycle")
                nb_funds_exhausted = True
                break
            if nb_result.already_placed:
                state.record_nb_placed(match.match_key)
                log.info("NB tip ALREADY EXISTS: %s %s (skipped)", match.match_key, decision.bet_type)
            elif nb_result.success:
                stats.nb_placed += 1
                state.record_nb_placed(match.match_key)
                log.info("NB tip OK: %s %s", match.match_key, decision.bet_type)
            else:
                log.warning("NB tip FAIL: %s -- %s", match.match_key, nb_result.error)

        # Far-future decided matches [B1 fix]
        if not nb_funds_exhausted:
            for far_match, bet_type, _lr in far_decided:
                if state.is_nb_placed(far_match.match_key):
                    continue
                nb_result = nb_placer.place_tip(
                    far_match, bet_type, config.nb.dry_run,
                )
                if nb_result.insufficient_funds:
                    log.warning("NB insufficient funds (far) — stopping NB bets this cycle")
                    break
                if nb_result.already_placed:
                    state.record_nb_placed(far_match.match_key)
                    log.info("NB tip ALREADY EXISTS (far): %s %s (skipped)", far_match.match_key, bet_type)
                elif nb_result.success:
                    stats.nb_placed += 1
                    state.record_nb_placed(far_match.match_key)
                    log.info("NB tip OK (far): %s %s", far_match.match_key, bet_type)
                else:
                    log.warning("NB tip FAIL (far): %s -- %s", far_match.match_key, nb_result.error)

    # Update nb_placed field in far-future rows that were just written
    # (rows are already in buffer — update in-place)
    for row in excel_writer._rows:
        # Find the match_key for this row to check nb_placed status
        # We stored rows in order, so match by link (unique per match)
        pass  # nb_placed is set below after all NB placement is done

    # Post-NB-placement: fill nb_placed for all buffered rows
    _update_nb_placed_flags(excel_writer, state, far_decided, passing)

    if not passing:
        log.info("No passing decisions for near-window matches")
        if excel_writer.row_count > 0:
            try:
                excel_writer.save()
            except Exception:
                log.exception("Failed to save Excel")
                stats.errors += 1
        return stats

    # 4. Kush session and matching
    try:
        kush_session = KushSession(
            base_url=config.kush.base_url,
            proxy=proxies[0] if proxies else None,
        )
        kush_session.init_csrf()
        kush_client = KushClient(kush_session)
        all_events = kush_client.get_all_events(day=0)
        for extra_day in (1, 2):
            extra = kush_client.get_all_events(day=extra_day)
            if not extra:
                break
            all_events.extend(extra)
        log.info("Fetched %d Kush events (day 0-2)", len(all_events))
    except Exception:
        log.exception("Failed to connect to Kush")
        stats.errors += 1
        return stats

    matcher = EventMatcher(
        time_tolerance_hours=config.kush.match_time_tolerance_hours,
        min_confidence=config.kush.min_confidence,
        tracker=tracker,
    )

    bet_placer = BetPlacer(
        session=kush_session,
        client=kush_client,
        thresholds=config.thresholds,
        kush_config=config.kush,
    )

    now_str_date = datetime.now().strftime("%d.%m.%Y")
    now_str_time = datetime.now().strftime("%H:%M")

    # 5. Match and place bets (one bet type per match)
    for match, decision, league_roi in passing:
        kush_league = league_filter.get_kush_league(match.league)
        log.info(
            "Matching: %s | NB time=%s | kush_league=%s | kush_events=%d",
            match.match_key,
            match.start_time_utc.strftime("%H:%M %d.%m.%Y"),
            kush_league or "(no mapping)",
            len(all_events),
        )
        result = matcher.find_best_match(match, all_events, kush_league_name=kush_league)

        kf_nb = _get_kf_nb(match, decision.bet_type)
        threshold = bet_placer.get_threshold(match.league)
        effective_roi = league_roi if league_roi else config.thresholds.roi
        min_kf = (threshold * kf_nb / (1 + effective_roi)) if kf_nb and kf_nb > 0 else 0.0
        is_nb = "+" if state.is_nb_placed(match.match_key) else "-"

        if result is None:
            # --- Missing on Kush ---
            stats.missing += 1
            was_new = state.enqueue_pending(match.match_key, [decision.bet_type])

            excel_writer.add_row(UnifiedRow(
                date=match.start_time_utc.strftime("%d.%m.%Y"),
                time=match.start_time_utc.strftime("%H:%M"),
                league=match.league,
                team_home=match.team_home,
                team_away=match.team_away,
                bet_type=decision.bet_type,
                kf1_start=_fmt(match.odds_1_start),
                kfx_start=_fmt(match.odds_x_start),
                kf2_start=_fmt(match.odds_2_start),
                kf_nb=_fmt(kf_nb),
                min_kf_kush=_fmt(min_kf),
                nb_placed=is_nb,
                kush_placed="-",
                kush_reason="отсутствие",
                kf_kush="",
                kush_date="",
                kush_time="",
                link=match.nb_url,
            ))

            if was_new:
                telegram.notify_missing(
                    match_key=match.match_key,
                    league=match.league,
                    team_home=match.team_home,
                    team_away=match.team_away,
                    match_time=match.start_time_utc.strftime("%H:%M"),
                    match_date=match.start_time_utc.strftime("%d.%m.%Y"),
                    bet_type=decision.bet_type,
                    odds_1=_fmt(match.odds_1_start),
                    odds_x=_fmt(match.odds_x_start),
                    odds_2=_fmt(match.odds_2_start),
                    link=match.nb_url,
                )
            continue

        stats.matched += 1
        kush_event = result.kush_event

        # Track was_pending status before removing from pending
        was_pending = state.was_previously_pending(match.match_key)
        state.remove_pending(match.match_key)

        try:
            if kf_nb is None or kf_nb <= 0:
                log.warning("No NB odds for %s on %s", decision.bet_type, match.match_key)
                excel_writer.add_row(UnifiedRow(
                    date=match.start_time_utc.strftime("%d.%m.%Y"),
                    time=match.start_time_utc.strftime("%H:%M"),
                    league=match.league,
                    team_home=match.team_home,
                    team_away=match.team_away,
                    bet_type=decision.bet_type,
                    kf1_start=_fmt(match.odds_1_start),
                    kfx_start=_fmt(match.odds_x_start),
                    kf2_start=_fmt(match.odds_2_start),
                    kf_nb="",
                    min_kf_kush="",
                    nb_placed=is_nb,
                    kush_placed="-",
                    kush_reason="нет кф НБ",
                    kf_kush="",
                    kush_date="",
                    kush_time="",
                    link=match.nb_url,
                ))
                continue

            bet_type_kush = _to_kush_bet_type(decision.bet_type)

            bet_result = bet_placer.place_bet(
                match=match,
                kush_event_id=kush_event.event_id,
                kush_event_url=kush_event.url,
                bet_type_kush=bet_type_kush,
                kf_nb=kf_nb,
                dry_run=config.kush.dry_run,
                roi=league_roi,
            )
            if bet_result.success:
                # --- Placed on Kush ---
                stats.placed += 1
                if state.is_ratio_rejected(match.match_key):
                    state.promote_to_placed(match.match_key)
                else:
                    state.record_placed(match.match_key)

                excel_writer.add_row(UnifiedRow(
                    date=match.start_time_utc.strftime("%d.%m.%Y"),
                    time=match.start_time_utc.strftime("%H:%M"),
                    league=match.league,
                    team_home=match.team_home,
                    team_away=match.team_away,
                    bet_type=bet_result.bet_type,
                    kf1_start=_fmt(match.odds_1_start),
                    kfx_start=_fmt(match.odds_x_start),
                    kf2_start=_fmt(match.odds_2_start),
                    kf_nb=_fmt(kf_nb),
                    min_kf_kush=_fmt(min_kf),
                    nb_placed=is_nb,
                    kush_placed="+",
                    kush_reason="",
                    kf_kush=f"{bet_result.kf_kush:.2f}",
                    kush_date=now_str_date,
                    kush_time=now_str_time,
                    link=match.nb_url,
                ))

                # TG notification only for matches that were previously pending [B4]
                if was_pending and state.record_tg_notified_kush(match.match_key):
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
                        match_time=match.start_time_utc.strftime("%H:%M"),
                        match_date=match.start_time_utc.strftime("%d.%m.%Y"),
                        odds_1=_fmt(match.odds_1_start),
                        odds_x=_fmt(match.odds_x_start),
                        odds_2=_fmt(match.odds_2_start),
                        link=match.nb_url,
                        was_pending=was_pending,
                    )
            elif bet_result.insufficient_funds:
                # --- Insufficient funds on Kush ---
                log.warning("Kush insufficient funds — stopping Kush bets this cycle")
                excel_writer.add_row(UnifiedRow(
                    date=match.start_time_utc.strftime("%d.%m.%Y"),
                    time=match.start_time_utc.strftime("%H:%M"),
                    league=match.league,
                    team_home=match.team_home,
                    team_away=match.team_away,
                    bet_type=bet_result.bet_type,
                    kf1_start=_fmt(match.odds_1_start),
                    kfx_start=_fmt(match.odds_x_start),
                    kf2_start=_fmt(match.odds_2_start),
                    kf_nb=_fmt(kf_nb),
                    min_kf_kush=_fmt(min_kf),
                    nb_placed=is_nb,
                    kush_placed="-",
                    kush_reason="нет средств",
                    kf_kush=_fmt(bet_result.kf_kush),
                    kush_date="",
                    kush_time="",
                    link=match.nb_url,
                ))
                # Don't mark as processed — retry next cycle
                break
            elif not bet_result.ratio_passes and bet_result.kf_kush > 0:
                # --- Ratio rejected ---
                stats.rejected += 1
                state.record_ratio_rejected(match.match_key)

                excel_writer.add_row(UnifiedRow(
                    date=match.start_time_utc.strftime("%d.%m.%Y"),
                    time=match.start_time_utc.strftime("%H:%M"),
                    league=match.league,
                    team_home=match.team_home,
                    team_away=match.team_away,
                    bet_type=bet_result.bet_type,
                    kf1_start=_fmt(match.odds_1_start),
                    kfx_start=_fmt(match.odds_x_start),
                    kf2_start=_fmt(match.odds_2_start),
                    kf_nb=f"{bet_result.kf_nb:.2f}",
                    min_kf_kush=_fmt(min_kf),
                    nb_placed=is_nb,
                    kush_placed="-",
                    kush_reason="ratio",
                    kf_kush=f"{bet_result.kf_kush:.2f}",
                    kush_date="",
                    kush_time="",
                    link=match.nb_url,
                ))

                log.info(
                    "Ratio rejected: %s ratio=%.3f threshold=%.2f",
                    match.match_key, bet_result.ratio, bet_result.threshold,
                )
            else:
                log.warning("Bet failed: %s", bet_result.summary)
                excel_writer.add_row(UnifiedRow(
                    date=match.start_time_utc.strftime("%d.%m.%Y"),
                    time=match.start_time_utc.strftime("%H:%M"),
                    league=match.league,
                    team_home=match.team_home,
                    team_away=match.team_away,
                    bet_type=decision.bet_type,
                    kf1_start=_fmt(match.odds_1_start),
                    kfx_start=_fmt(match.odds_x_start),
                    kf2_start=_fmt(match.odds_2_start),
                    kf_nb=_fmt(kf_nb),
                    min_kf_kush=_fmt(min_kf),
                    nb_placed=is_nb,
                    kush_placed="-",
                    kush_reason=f"ошибка: {bet_result.error[:50]}" if bet_result.error else "ошибка",
                    kf_kush=_fmt(bet_result.kf_kush),
                    kush_date="",
                    kush_time="",
                    link=match.nb_url,
                ))
                state.record_processed(match.match_key)
        except Exception:
            log.exception("Error placing bet for %s", match.match_key)
            stats.errors += 1

    # 6. Save Excel (if any rows)
    if excel_writer.row_count > 0:
        try:
            excel_writer.save()
        except Exception:
            log.exception("Failed to save Excel")
            stats.errors += 1

    # 7. Flush near-misses to file
    if tracker:
        tracker.flush_near_misses()

    log.info(
        "Cycle done: %d total, %d filtered, %d decided, %d matched, "
        "%d placed, %d missing, %d rejected, %d pending, %d nb_placed, %d errors",
        stats.total_matches,
        stats.filtered,
        stats.decided,
        stats.matched,
        stats.placed,
        stats.missing,
        stats.rejected,
        stats.pending,
        stats.nb_placed,
        stats.errors,
    )

    return stats


def _update_nb_placed_flags(
    excel_writer: ExcelWriter,
    state: AppState,
    far_decided: list[tuple],
    passing: list[tuple],
) -> None:
    """Fill nb_placed field for far-future rows already in buffer."""
    # Build a link->nb_placed map from far_decided matches
    link_to_nb: dict[str, str] = {}
    for far_match, _bt, _roi in far_decided:
        flag = "+" if state.is_nb_placed(far_match.match_key) else "-"
        link_to_nb[far_match.nb_url] = flag

    for row in excel_writer._rows:
        if row.nb_placed == "" and row.link in link_to_nb:
            row.nb_placed = link_to_nb[row.link]


def _get_kf_nb(match: Match, bet_type: str) -> Optional[float]:
    """Extract the appropriate NB START coefficient for a given bet type.

    Uses START odds (not END) because the ratio formula compares opening lines.
    """
    bt = bet_type.upper()
    if bt in ("1", "П1"):
        return match.odds_1_start
    elif bt in ("2", "П2"):
        return match.odds_2_start
    elif bt in ("X", "НИЧЬЯ"):
        return match.odds_x_start
    return match.odds_1_start  # fallback
