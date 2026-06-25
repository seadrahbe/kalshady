#!/usr/bin/env python3
"""Print live markets with their IDs, outcome IDs, prices, and pools (for admin ops)."""
import json
import sys
import urllib.request

API = "http://127.0.0.1:8010"
ms = json.load(urllib.request.urlopen(f"{API}/api/markets"))
for m in ms:
    print(f"\n● {m['title']}")
    print(f"  market_id : {m['id']}")
    print(f"  status={m['status']}  rake={m['rake_bps'] // 100}%  pool={m['total_pool_cents'] / 100:.0f} SB")
    for o in m["outcomes"]:
        print(f"    - {o['label']:4} outcome_id={o['id']}  price={o['price_cents']}c  pool={o['pool_cents'] / 100:.0f} SB")
