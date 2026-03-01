"""Diagnostic: check if matches pass decision engine (league filter + conditions)."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.nb.client import NbClient
from src.config.schema import NbConfig
from src.config.loader import load_config
from src.decision.league_loader import load_league_settings
from src.decision.league_filter import LeagueFilter, load_chemps_zamen

TARGET_SLUGS = [
    "nyuells-old-boyz-estudiantes",
    "viktoriya-plzen-panatinaikos",
]

def main():
    # Load config
    try:
        config = load_config("config.json")
    except Exception as e:
        print(f"Config load error: {e}, using defaults")
        config = None

    # Load leagues
    settings = load_league_settings("leagues.xlsx")
    chemps = load_chemps_zamen()
    lf = LeagueFilter(settings, chemps)

    print(f"Loaded {len(settings)} league groups, {len(chemps)} chemps_zamen entries\n")

    # Fetch NB
    nb_config = NbConfig()
    nb = NbClient(nb_config)
    matches = nb.get_matches(sport="soccer", window_days=3)
    print(f"NB: {len(matches)} matches\n")

    for m in matches:
        for slug in TARGET_SLUGS:
            if slug not in (m.nb_slug or ""):
                continue

            print(f"=== {m.nb_slug} ===")
            print(f"  League: {m.league}")
            print(f"  Teams:  {m.team_home} vs {m.team_away}")
            print(f"  Time:   {m.start_time_utc.strftime('%H:%M %d.%m.%Y')}")
            print(f"  kf1_end={m.odds_1_end}  kfX_end={m.odds_x_end}  kf2_end={m.odds_2_end}")
            print(f"  kf1_start={m.odds_1_start}  kfX_start={m.odds_x_start}  kf2_start={m.odds_2_start}")
            print()

            # 1. League filter
            allowed = lf._is_league_allowed(m.league)
            print(f"  League allowed: {allowed}")

            if not allowed:
                print(f"  -> REJECTED at league filter stage (not in leagues.xlsx)")
                kush_name = chemps.get(m.league)
                print(f"  chemps_zamen mapping: '{m.league}' -> '{kush_name}'")
                # Check close matches
                for s in settings:
                    for lg in s.leagues:
                        if any(w in lg.lower() for w in m.league.lower().split(". ")[-1].split()[:2]):
                            print(f"    Possible match in xlsx: '{lg}' (bet={s.bet_type})")
                print()
                continue

            # 2. Find setting
            setting = lf.find_setting(m)
            print(f"  Setting found: {setting is not None}")
            if setting:
                print(f"    bet_type: {setting.bet_type}")
                print(f"    condition: {setting.condition_raw}")
                print(f"    roi: {setting.roi}")
                print(f"    kf_relation: {setting.kf_relation}")
                print(f"    min_kf1={setting.min_kf1} max_kf1={setting.max_kf1}")
                print(f"    min_kf2={setting.min_kf2} max_kf2={setting.max_kf2}")

                # 3. Check conditions
                passes = setting.check(m.odds_1_end, m.odds_2_end)
                print(f"    check(kf1={m.odds_1_end}, kf2={m.odds_2_end}): {passes}")

                if not passes:
                    print(f"    -> REJECTED at decision stage")
                    # Show which condition failed
                    kf1, kf2 = m.odds_1_end, m.odds_2_end
                    if kf1 < setting.min_kf1: print(f"       kf1 {kf1} < min_kf1 {setting.min_kf1}")
                    if kf1 > setting.max_kf1: print(f"       kf1 {kf1} > max_kf1 {setting.max_kf1}")
                    if kf2 < setting.min_kf2: print(f"       kf2 {kf2} < min_kf2 {setting.min_kf2}")
                    if kf2 > setting.max_kf2: print(f"       kf2 {kf2} > max_kf2 {setting.max_kf2}")
                    if setting.kf_relation == "kf1>kf2" and not (kf1 > kf2):
                        print(f"       relation kf1>kf2 FAIL: {kf1} <= {kf2}")
                    if setting.kf_relation == "kf1<kf2" and not (kf1 < kf2):
                        print(f"       relation kf1<kf2 FAIL: {kf1} >= {kf2}")
                else:
                    print(f"    -> PASSED decision, would go to matcher")

            # Also check ALL settings for this league
            all_settings = lf.find_all_settings(m)
            if len(all_settings) > 1:
                print(f"\n  All settings for this league ({len(all_settings)}):")
                for s in all_settings:
                    p = s.check(m.odds_1_end, m.odds_2_end)
                    print(f"    bet={s.bet_type} cond='{s.condition_raw}' check={p}")

            print()


if __name__ == "__main__":
    main()
