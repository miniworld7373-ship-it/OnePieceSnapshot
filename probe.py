#!/usr/bin/env python3
"""One-off: how often does CardTrader refresh the per-expansion marketplace cache?

Every 60 s for MINUTES: fetch two busy One Piece expansions in bulk, note ETag and a
fingerprint (listings, total quantity, total price).  A new fingerprint = a refresh.
Log printed and stored in R2 (measure/probe-<stamp>.txt).
"""
import hashlib
import os
import time
from datetime import datetime, timezone

from snapshot import W, WORKER, get, s, API

MINUTES = int(os.environ.get("MINUTES", "120"))
exps = [e for e in get("expansions") if e["game_id"] == 15 and e["code"] in ("op16", "op15")]
log, last = [], {}
for i in range(MINUTES):
    t0 = time.time()
    for e in exps:
        r = s.get(f"{API}/marketplace/products", params={"expansion_id": e["id"]}, timeout=120)
        ls = [l for v in r.json().values() for l in v]
        fp = hashlib.md5(repr(sorted((l["id"], l["price_cents"], l["quantity"]) for l in ls)).encode()).hexdigest()[:8]
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        line = f"{now} {e['code']} n={len(ls)} fp={fp} etag={r.headers.get('etag', '')[-10:]} {'REFRESH' if last.get(e['code']) not in (None, fp) else ''}"
        last[e["code"]] = fp
        print(line, flush=True)
        log.append(line)
    time.sleep(max(0, 60 - (time.time() - t0)))
stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
W.put(f"{WORKER}/put", params={"key": f"measure/probe-{stamp}.txt"}, data="\n".join(log).encode(), timeout=60)
