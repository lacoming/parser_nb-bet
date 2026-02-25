"""Full cycle orchestration.

One cycle: NB-Bet -> filter -> decide -> Kush match -> bet -> excel -> telegram.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.config.schema import AppConfig
from src.decision.league_filter import LeagueFilter
from src.decision.models import BetDecision
from src.excel.models import ExcelRow, MissingRow, PendingRow, RejectedRow
from src.excel.writer import ExcelWriter
from src.kush.bet_placer import BetPlacer
from src.kush.client import KushClient
from src.kush.matcher import EventMatcher
from src.kush.session import KushSession
from src.nb.client import NbClient
from src.nb.models import Match
from src.state import AppState
from src.telegram.notifier import TelegramNotifier

log = logging.getLogger("parser_nb_bet.scheduler.cycle_runner")

# Decision engine bet types → Kush bet types
_DECISION_TO_KUSH: dict[str, str] = {
    "1": "П1",
    "2": "П2",
    "X": "X",
    "1X": "1X",
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
        self.errors = 0


def _get_default_threshold(config: AppConfig, league: str) -> float:
    """Return ratio threshold for a league (big or default), without BetPlacer."""
    for big in config.thresholds.big_leagues:
        if big.lower() in league.lower():
            return config.thresholds.big_league_ratio
    return config.thresholds.default_ratio


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
        link=match.nb_url,
    )


def run_cycle(
    config: AppConfig,
    state: AppState,
    nb_client: NbClient,
    league_filter: LeagueFilter,
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

    # 2b. Skip matches outside Kush's window (day 0/1/2 = up to 3 calendar days)
    # Kush serves day=0 (today), day=1 (tomorrow), day=2 (day after).
    # Filter NB matches to end-of-day+2 MSK to avoid false kush-off alerts.
    _MSK_OFFSET = timedelta(hours=3)
    now_msk = datetime.now(timezone.utc) + _MSK_OFFSET
    kush_max_date = now_msk.replace(
        hour=23, minute=59, second=59, microsecond=0,
    ) + timedelta(days=2)
    near_matches = [m for m in filtered if m.start_time_utc <= kush_max_date]
    far_matches = [m for m in filtered if m.start_time_utc > kush_max_date]
    if far_matches:
        log.info(
            "%d matches beyond Kush window (after %s MSK) → pending sheet",
            len(far_matches),
            kush_max_date.strftime("%d.%m %H:%M"),
        )

    # 2b-2. Process far-future matches through decision engine → pending sheet + TG
    for far_match in far_matches:
        setting = league_filter.find_setting(far_match)
        if not setting:
            continue
        if not setting.check(far_match.odds_1_end, far_match.odds_2_end):
            continue
        target_bet_type = setting.bet_type
        league_roi = setting.roi
        kf_nb = _get_kf_nb(far_match, target_bet_type)
        threshold = _get_default_threshold(config, far_match.league)
        effective_roi = league_roi if league_roi else config.thresholds.roi
        min_kf = (threshold * kf_nb / (1 + effective_roi)) if kf_nb and kf_nb > 0 else 0.0
        excel_writer.add_pending_row(PendingRow(
            date=far_match.start_time_utc.strftime("%d.%m.%Y"),
            time=far_match.start_time_utc.strftime("%H:%M"),
            league=far_match.league,
            team_home=far_match.team_home,
            team_away=far_match.team_away,
            bet_type=target_bet_type,
            odds_1_start=f"{far_match.odds_1_start:.2f}" if far_match.odds_1_start else "",
            odds_x_start=f"{far_match.odds_x_start:.2f}" if far_match.odds_x_start else "",
            odds_2_start=f"{far_match.odds_2_start:.2f}" if far_match.odds_2_start else "",
            kf_nb=f"{kf_nb:.2f}" if kf_nb else "",
            min_kf_kush=f"{min_kf:.2f}" if min_kf else "",
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
                odds_1=f"{far_match.odds_1_start:.2f}" if far_match.odds_1_start else "",
                odds_x=f"{far_match.odds_x_start:.2f}" if far_match.odds_x_start else "",
                odds_2=f"{far_match.odds_2_start:.2f}" if far_match.odds_2_start else "",
                link=far_match.nb_url,
            )

    # 2c. Skip already-processed matches (Bug 3 fix)
    new_matches = [m for m in near_matches if not state.is_processed(m.match_key)]
    skipped = len(filtered) - len(new_matches)
    if skipped:
        log.info("Skipped %d already-processed matches", skipped)

    # 3. Decision engine — one bet type per match from leagues.xlsx
    passing: list[tuple[Match, BetDecision, float]] = []
    for match in new_matches:
        setting = league_filter.find_setting(match)
        if not setting:
            log.debug("No league setting for %s", match.match_key)
            continue
        league_roi = setting.roi
        # The league setting defines the ONE bet type for this group
        target_bet_type = setting.bet_type  # "1" | "2" | "1X" | "X"
        # Check if match odds satisfy the league conditions
        if not setting.check(match.odds_1_end, match.odds_2_end):
            log.debug(
                "Conditions not met for %s bet=%s: kf1=%s kf2=%s",
                match.match_key, target_bet_type, match.odds_1_end, match.odds_2_end,
            )
            continue
        decision = BetDecision(
            bet_type=target_bet_type,
            passes=True,
            reasons=[f"league: {setting.condition_raw}"],
        )
        passing.append((match, decision, league_roi))
    stats.decided = len(passing)
    log.info("Decision engine: %d matches with passing bets", stats.decided)

    if not passing:
        log.info("No passing decisions for near-window matches")
        # Still save Excel if pending rows exist from far-future processing
        if excel_writer.pending_count > 0:
            try:
                path = excel_writer.save()
                telegram.send_document(path, caption="Результаты цикла")
            except Exception:
                log.exception("Failed to save Excel")
                stats.errors += 1
        telegram.notify_cycle_summary(
            total_matches=stats.total_matches,
            filtered=stats.filtered,
            decided=0,
            matched=0,
            placed=0,
            missing=0,
            errors=stats.errors,
            dry_run=config.kush.dry_run,
            pending=stats.pending,
            rejected=stats.rejected,
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
        # Fetch events for today + tomorrow + day after (Kush serves up to 3 days)
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

        if result is None:
            stats.missing += 1
            if state.enqueue_pending(match.match_key, [decision.bet_type]):
                telegram.notify_missing(
                    match_key=match.match_key,
                    league=match.league,
                    team_home=match.team_home,
                    team_away=match.team_away,
                    match_time=match.start_time_utc.strftime("%H:%M"),
                    match_date=match.start_time_utc.strftime("%d.%m.%Y"),
                    bet_type=decision.bet_type,
                    odds_1=f"{match.odds_1_start:.2f}" if match.odds_1_start else "",
                    odds_x=f"{match.odds_x_start:.2f}" if match.odds_x_start else "",
                    odds_2=f"{match.odds_2_start:.2f}" if match.odds_2_start else "",
                    link=match.nb_url,
                )
            kf_nb = _get_kf_nb(match, decision.bet_type)
            threshold = bet_placer.get_threshold(match.league)
            effective_roi = league_roi if league_roi else config.thresholds.roi
            min_kf = (threshold * kf_nb / (1 + effective_roi)) if kf_nb and kf_nb > 0 else 0.0
            excel_writer.add_missing_row(MissingRow(
                date=match.start_time_utc.strftime("%d.%m.%Y"),
                time=match.start_time_utc.strftime("%H:%M"),
                league=match.league,
                team_home=match.team_home,
                team_away=match.team_away,
                bet_type=decision.bet_type,
                odds_1_start=f"{match.odds_1_start:.2f}" if match.odds_1_start else "",
                odds_x_start=f"{match.odds_x_start:.2f}" if match.odds_x_start else "",
                odds_2_start=f"{match.odds_2_start:.2f}" if match.odds_2_start else "",
                kf_nb=f"{kf_nb:.2f}" if kf_nb else "",
                min_kf_kush=f"{min_kf:.2f}" if min_kf else "",
                link=match.nb_url,
            ))
            # NOT record_processed — missing matches must be rechecked next cycle
            continue

        stats.matched += 1
        kush_event = result.kush_event

        # If previously missing (pending), remove from pending queue
        state.remove_pending(match.match_key)

        try:
            # Determine which NB odds to use for ratio
            kf_nb = _get_kf_nb(match, decision.bet_type)
            if kf_nb is None or kf_nb <= 0:
                log.warning("No NB odds for %s on %s", decision.bet_type, match.match_key)
                continue

            # Translate decision bet type to Kush format (e.g. "1" → "П1")
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
                stats.placed += 1
                # If previously ratio-rejected, promote; otherwise record placed
                if state.is_ratio_rejected(match.match_key):
                    state.promote_to_placed(match.match_key)
                else:
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
                    match_time=match.start_time_utc.strftime("%H:%M"),
                    match_date=match.start_time_utc.strftime("%d.%m.%Y"),
                    odds_1=f"{match.odds_1_start:.2f}" if match.odds_1_start else "",
                    odds_x=f"{match.odds_x_start:.2f}" if match.odds_x_start else "",
                    odds_2=f"{match.odds_2_start:.2f}" if match.odds_2_start else "",
                    link=match.nb_url,
                )
            elif not bet_result.ratio_passes and bet_result.kf_kush > 0:
                # Ratio-rejected: record for recheck, write to rejected sheet
                stats.rejected += 1
                state.record_ratio_rejected(match.match_key)
                excel_writer.add_rejected_row(RejectedRow(
                    date=match.start_time_utc.strftime("%d.%m.%Y"),
                    time=match.start_time_utc.strftime("%H:%M"),
                    league=match.league,
                    team_home=match.team_home,
                    team_away=match.team_away,
                    bet_type=bet_result.bet_type,
                    odds_1_start=f"{match.odds_1_start:.2f}" if match.odds_1_start else "",
                    odds_x_start=f"{match.odds_x_start:.2f}" if match.odds_x_start else "",
                    odds_2_start=f"{match.odds_2_start:.2f}" if match.odds_2_start else "",
                    kf_nb=f"{bet_result.kf_nb:.2f}",
                    kf_kush=f"{bet_result.kf_kush:.2f}",
                    ratio=f"{bet_result.ratio:.3f}",
                    threshold=f"{bet_result.threshold:.2f}",
                    link=match.nb_url,
                ))
                telegram.notify_ratio_rejected(
                    match_key=match.match_key,
                    bet_type=bet_result.bet_type,
                    kf_nb=bet_result.kf_nb,
                    kf_kush=bet_result.kf_kush,
                    ratio=bet_result.ratio,
                    threshold=bet_result.threshold,
                    league=match.league,
                    team_home=match.team_home,
                    team_away=match.team_away,
                    match_time=match.start_time_utc.strftime("%H:%M"),
                    match_date=match.start_time_utc.strftime("%d.%m.%Y"),
                    odds_1=f"{match.odds_1_start:.2f}" if match.odds_1_start else "",
                    odds_x=f"{match.odds_x_start:.2f}" if match.odds_x_start else "",
                    odds_2=f"{match.odds_2_start:.2f}" if match.odds_2_start else "",
                    link=match.nb_url,
                )
                log.info(
                    "Ratio rejected: %s ratio=%.3f threshold=%.2f",
                    match.match_key, bet_result.ratio, bet_result.threshold,
                )
            else:
                log.warning("Bet failed: %s", bet_result.summary)
                state.record_processed(match.match_key)
        except Exception:
            log.exception("Error placing bet for %s", match.match_key)
            stats.errors += 1

    # 6. Save Excel (if any data in any sheet)
    if excel_writer.row_count > 0 or excel_writer.missing_count > 0 or excel_writer.rejected_count > 0 or excel_writer.pending_count > 0:
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
        pending=stats.pending,
        rejected=stats.rejected,
    )

    log.info(
        "Cycle done: %d total, %d filtered, %d decided, %d matched, "
        "%d placed, %d missing, %d rejected, %d pending, %d errors",
        stats.total_matches,
        stats.filtered,
        stats.decided,
        stats.matched,
        stats.placed,
        stats.missing,
        stats.rejected,
        stats.pending,
        stats.errors,
    )

    return stats


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
    elif bt in ("1X",):
        # Bug 2 fix: 1X ratio uses kf1 (not min(kf1, kfX))
        return match.odds_1_start
    return match.odds_1_start  # fallback
