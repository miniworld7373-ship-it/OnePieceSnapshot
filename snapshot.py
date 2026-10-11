#!/usr/bin/env python3
"""Snapshot 100 % of One Piece listings on CardTrader; store only what changed, in R2.

Read-only on CardTrader.  Every One Piece expansion, every language, condition and seller:
filter at analysis time, never at collection time.  One row per listing.

R2 (through the Worker, see trigger/index.js):
  state/full.csv.gz              previous snapshot, the diff reference (overwritten)
  diffs/<YYYYMMDD>/<HHMM>.csv.gz  event (new / chg / gone) + listing row, UTC
  base/<YYYYMMDD>.csv.gz          first full snapshot of each UTC day (recompute anchor)
A snapshot where an expansion failed is dropped whole: a missing expansion would read
as thousands of sales.

    CARDTRADER_TOKEN=... WORKER_URL=... UPLOAD_KEY=... python snapshot.py
"""
import csv
import gzip
import io
import os
import sys
import time
from datetime import datetime, timezone

import requests

API = "https://api.cardtrader.com/api/v2"
ONE_PIECE = 15
FIELDS = ["listing_id", "blueprint_id", "number", "name", "expansion", "rarity", "price_cents", "currency",
          "quantity", "condition", "language", "signed", "altered", "graded", "on_vacation", "seller_id",
          "seller", "country", "zero", "one_day_ready", "user_type"]

s = requests.Session()
s.headers["Authorization"] = f"Bearer {os.environ['CARDTRADER_TOKEN']}"


def get(path, **params):
    for attempt in range(6):
        try:
            r = s.get(f"{API}/{path}", params=params, timeout=120)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(str(r.status_code))
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            print(f"  ! {path} {params} attempt {attempt + 1}: {exc}", flush=True)
            time.sleep(2 ** attempt)
    return None


def row(l, exp):
    ph = l.get("properties_hash") or {}
    u = l.get("user") or {}
    b = lambda v: int(bool(v))  # noqa: E731
    return [l["id"], l["blueprint_id"], ph.get("collector_number", ""), l.get("name_en", ""), exp,
            ph.get("onepiece_rarity", ""), l["price_cents"], l.get("price_currency", ""), l.get("quantity"),
            ph.get("condition", ""), ph.get("onepiece_language", ""), b(ph.get("signed")), b(ph.get("altered")),
            b(l.get("graded")), b(l.get("on_vacation")), u.get("id"), u.get("username", ""),
            u.get("country_code", ""), b(u.get("can_sell_via_hub")), b(u.get("one_day_ready")), u.get("user_type", "")]


W = requests.Session()
W.headers["X-Key"] = os.environ.get("UPLOAD_KEY", "")
WORKER = os.environ.get("WORKER_URL", "").rstrip("/")


def gz(header, rows):
    buf = io.BytesIO()
    with gzip.open(buf, "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return buf.getvalue()


def put(key, data):
    r = W.put(f"{WORKER}/put", params={"key": key}, data=data, timeout=300)
    r.raise_for_status()


def fetch_state():
    r = W.get(f"{WORKER}/get", params={"key": "state/full.csv.gz"}, timeout=300)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    with gzip.open(io.BytesIO(r.content), "rt", newline="") as f:
        return {row[0]: row for row in list(csv.reader(f))[1:]}


def diff(prev, rows):
    """``[event] + row`` for listings new, changed, or gone since ``prev``."""
    out, now = [], set()
    for r in rows:
        now.add(r[0])
        old = prev.get(r[0])
        if old is None:
            out.append(["new"] + r)
        elif old != r:
            out.append(["chg"] + r)
    out += [["gone"] + r for k, r in prev.items() if k not in now]
    return out


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    t0 = time.time()
    exps = [e for e in get("expansions") or [] if e["game_id"] == ONE_PIECE]
    if not exps:
        sys.exit("no expansions")
    rows, failed = [], 0
    for e in exps:
        body = get("marketplace/products", expansion_id=e["id"])
        if body is None:
            failed += 1
            continue
        for listings in body.values():
            rows += [["" if v is None else str(v) for v in row(l, e["code"])] for l in listings]
        time.sleep(0.2)
    if failed:
        sys.exit(f"{stamp}: {failed} expansion(s) failed, snapshot dropped")
    day, hm = stamp.split("-")
    prev = fetch_state()
    state = gz(FIELDS, rows)
    msg = "first snapshot"
    if prev is not None:
        d = diff(prev, rows)
        put(f"diffs/{day}/{hm}.csv.gz", gz(["event"] + FIELDS, d))
        msg = f"{len(d)} changes"
    if prev is None or hm < "0010":
        put(f"base/{day}.csv.gz", state)
    put("state/full.csv.gz", state)
    print(f"{stamp}: {len(rows)} listings, {len(exps)} expansions, {msg}, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
