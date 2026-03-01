"""Diagnostic: check how many days Kush supports (day=0,1,2,3...)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from src.kush.session import KushSession
from src.kush.client import KushClient

session = KushSession(base_url="https://kushvsporte.ru")
session.init_csrf()
client = KushClient(session)

for day in range(15):
    try:
        events = client.get_all_events(day=day)
        print(f"day={day}: {len(events)} events")
        if events:
            # Show date range
            times = [e.start_time_utc for e in events]
            mn = min(times).strftime("%d.%m %H:%M")
            mx = max(times).strftime("%d.%m %H:%M")
            print(f"  range: {mn} — {mx}")
        if len(events) == 0:
            print("  -> empty, stopping")
            break
    except Exception as e:
        print(f"day={day}: ERROR {e}")
        break
