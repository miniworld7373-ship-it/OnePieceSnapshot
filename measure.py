#!/usr/bin/env python3
"""One-off: how big is a full snapshot of a game?  Per expansion: listings, seconds, MB.

Stores nothing but a per-expansion summary in R2 (measure/<game>-<stamp>.csv).
    GAME=magic python measure.py
"""
import csv
import io
import json
import os
import statistics
import time
from datetime import datetime, timezone

from snapshot import W, WORKER, get

game = os.environ.get("GAME", "magic").lower()
gid = next(g["id"] for g in get("games")["array"] if game in g["name"].lower())
lang_prop = {"magic": "mtg_language", "pokemon": "pokemon_language"}.get(game, f"{game}_language")
exps = [e for e in get("expansions") if e["game_id"] == gid]
print(f"{game}: game_id {gid}, {len(exps)} expansions", flush=True)

t_all, rows, floors = time.time(), [], []
for i, e in enumerate(exps, 1):
    t0 = time.time()
    body = get("marketplace/products", expansion_id=e["id"])
    dt = time.time() - t0
    if body is None:
        rows.append([e["code"], e["name"], -1, 0, 0, round(dt, 1), 0])
        continue
    size = len(json.dumps(body))
    n = sum(len(v) for v in body.values())
    for listings in body.values():
        ok = [l["price_cents"] for l in listings
              if (l.get("properties_hash") or {}).get("condition") == "Near Mint"
              and (l.get("properties_hash") or {}).get(lang_prop) == "en"
              and (l.get("user") or {}).get("can_sell_via_hub")]
        if ok:
            floors.append(min(ok))
    rows.append([e["code"], e["name"], n, len(body), size, round(dt, 1), 0])
    if i % 50 == 0:
        print(f"  {i}/{len(exps)} {time.time() - t_all:.0f}s {sum(r[2] for r in rows if r[2] > 0)} listings", flush=True)
    time.sleep(0.2)

total = sum(r[2] for r in rows if r[2] > 0)
mb = sum(r[4] for r in rows) / 1e6
print(f"\n{game}: {len(exps)} expansions, {total} listings, {len(floors)} cards with an EN/NM/Zero listing, "
      f"{time.time() - t_all:.0f}s, raw JSON {mb:.0f} MB, failed {sum(r[2] < 0 for r in rows)}")
for lo, hi in ((0, 50), (50, 100), (100, 200), (200, 500), (500, 2000), (2000, 10**9)):
    print(f"  floor {lo/100:>6.2f}-{hi/100 if hi < 10**9 else 'inf':>6} €: {sum(lo <= f < hi for f in floors)} cards")
print("  median floor:", statistics.median(floors) / 100 if floors else None)
for r in sorted(rows, key=lambda r: -r[2])[:10]:
    print(f"  {r[0]:8} {r[2]:8} listings {r[5]:6.1f}s  {r[1][:40]}")
buf = io.StringIO()
csv.writer(buf).writerows([["code", "name", "listings", "blueprints", "json_bytes", "seconds", "_"]] + rows)
stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
W.put(f"{WORKER}/put", params={"key": f"measure/{game}-{stamp}.csv"}, data=buf.getvalue().encode(), timeout=120)
