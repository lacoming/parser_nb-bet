"""Diagnostic: check NB vs Kush time for a specific match slug."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta, timezone
from src.nb.client import NbClient, _parse_response
from src.kush.session import KushSession
from src.kush.client import KushClient
from src.kush.matcher import EventMatcher
from src.config.schema import NbConfig
import requests
import json

# --- Config ---
TARGET_SLUGS = [
    "nyuells-old-boyz-estudiantes",
    "viktoriya-plzen-panatinaikos",
]

def fetch_nb_matches():
    """Fetch NB matches and find target slugs."""
    config = NbConfig()
    client = NbClient(config)
    matches = client.get_matches(sport="soccer", window_days=3)
    print(f"\n=== NB-Bet: {len(matches)} total matches ===\n")

    found = []
    for m in matches:
        for slug in TARGET_SLUGS:
            if slug in (m.nb_slug or ""):
                print(f"  FOUND: {m.nb_slug}")
                print(f"    league:  {m.league}")
                print(f"    teams:   {m.team_home} vs {m.team_away}")
                print(f"    time:    {m.start_time_utc.strftime('%H:%M %d.%m.%Y')} (stored as MSK-in-UTC)")
                print(f"    kf1={m.odds_1_end}  kfX={m.odds_x_end}  kf2={m.odds_2_end}")
                print(f"    kf1s={m.odds_1_start}  kfXs={m.odds_x_start}  kf2s={m.odds_2_start}")
                print(f"    key:     {m.match_key}")
                print()
                found.append(m)

    if not found:
        print("  None of the target slugs found in NB data.")
        print("  Searching by team names...")
        for m in matches:
            name = f"{m.team_home} {m.team_away}".lower()
            if any(k in name for k in ["ньюэллс", "эстудиантес", "пльзень", "панатинаикос", "plzen", "oldboy"]):
                print(f"  PARTIAL: {m.nb_slug}")
                print(f"    league:  {m.league}")
                print(f"    teams:   {m.team_home} vs {m.team_away}")
                print(f"    time:    {m.start_time_utc.strftime('%H:%M %d.%m.%Y')}")
                print()
                found.append(m)

    return found


def fetch_kush_events():
    """Fetch Kush events for today and tomorrow."""
    session = KushSession(base_url="https://kushvsporte.ru")
    session.init_csrf()
    client = KushClient(session)

    events_today = client.get_all_events(day=0)
    events_tomorrow = client.get_all_events(day=1)
    all_events = events_today + events_tomorrow

    print(f"\n=== Kush: {len(events_today)} today + {len(events_tomorrow)} tomorrow = {len(all_events)} total ===\n")

    # Find target events
    found = []
    for ev in all_events:
        name = f"{ev.team_home} {ev.team_away}".lower()
        if any(k in name for k in [
            "ньюэллс", "эстудиантес", "олд бойз",
            "пльзень", "панатинаикос", "виктория",
        ]):
            print(f"  FOUND: eid={ev.event_id}")
            print(f"    league:  {ev.league}")
            print(f"    teams:   {ev.team_home} vs {ev.team_away}")
            print(f"    time:    {ev.start_time_utc.strftime('%H:%M %d.%m.%Y')} (stored as MSK-in-UTC)")
            print(f"    url:     {ev.url}")
            print()
            found.append(ev)

    if not found:
        print("  Target events not found on Kush.")
        # Show events with similar times
        for t in ["01:30", "20:45"]:
            print(f"\n  Events near {t}:")
            for ev in all_events:
                if ev.start_time_utc.strftime("%H:%M") == t:
                    print(f"    eid={ev.event_id} {ev.team_home} vs {ev.team_away} ({ev.league})")

    return all_events, found


def test_matching(nb_matches, all_kush_events):
    """Run matcher on found NB matches."""
    if not nb_matches:
        print("\n=== No NB matches to test ===")
        return

    matcher = EventMatcher(time_tolerance_hours=2.0, min_confidence=0.80)

    print(f"\n=== Matcher test ===\n")
    for m in nb_matches:
        print(f"Matching: {m.team_home} vs {m.team_away} (NB time={m.start_time_utc.strftime('%H:%M %d.%m')})")

        # Show top 5 candidates by confidence
        results = []
        for ev in all_kush_events:
            r = matcher._score(m, ev)
            if r is not None:
                results.append((r, ev))

        results.sort(key=lambda x: x[0].confidence, reverse=True)

        if not results:
            print(f"  NO candidates passed time filter! All {len(all_kush_events)} events outside ±2h window.")
            # Show closest by time
            by_time = sorted(all_kush_events, key=lambda e: abs((m.start_time_utc - e.start_time_utc).total_seconds()))
            print(f"  Closest by time:")
            for ev in by_time[:5]:
                diff_h = (ev.start_time_utc - m.start_time_utc).total_seconds() / 3600
                print(f"    eid={ev.event_id} '{ev.team_home} vs {ev.team_away}' "
                      f"time={ev.start_time_utc.strftime('%H:%M %d.%m')} diff={diff_h:+.1f}h")
        else:
            print(f"  Top {min(5, len(results))} candidates:")
            for r, ev in results[:5]:
                diff_h = (ev.start_time_utc - m.start_time_utc).total_seconds() / 3600
                print(f"    eid={ev.event_id} '{ev.team_home} vs {ev.team_away}' "
                      f"time={ev.start_time_utc.strftime('%H:%M %d.%m')} diff={diff_h:+.1f}h "
                      f"conf={r.confidence:.2f} name={r.name_score:.2f} time={r.time_score:.2f}")
        print()


if __name__ == "__main__":
    print("=" * 70)
    print("DIAGNOSTIC: NB vs Kush time comparison")
    print(f"Now (UTC): {datetime.now(timezone.utc).strftime('%H:%M %d.%m.%Y')}")
    print(f"Now (MSK): {(datetime.now(timezone.utc) + timedelta(hours=3)).strftime('%H:%M %d.%m.%Y')}")
    print("=" * 70)

    nb_matches = fetch_nb_matches()
    all_kush, kush_found = fetch_kush_events()
    test_matching(nb_matches, all_kush)
