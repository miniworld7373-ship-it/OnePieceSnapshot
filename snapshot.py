#!/usr/bin/env python3
"""One snapshot of 100 % of One Piece listings on CardTrader -> op-<YYYYMMDD-HHMM>Z.csv.gz

Read-only.  Every One Piece expansion, every language, condition and seller: filter at
analysis time, never at collection time.  One row per listing.  If an expansion still
fails after retries the file is named ``...-partial.csv.gz``: never read disappearances
from a partial snapshot.

    CARDTRADER_TOKEN=... python snapshot.py
"""
import csv
import gzip
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
            rows += [row(l, e["code"]) for l in listings]
        time.sleep(0.2)
    path = f"op-{stamp}Z{'-partial' if failed else ''}.csv.gz"
    with gzip.open(path, "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        w.writerows(rows)
    print(f"{path}: {len(rows)} listings, {len(exps)} expansions, {failed} failed, {time.time() - t0:.0f}s, "
          f"{os.path.getsize(path) / 1e6:.1f} MB", flush=True)
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f:
        f.write(f"file={path}\n")


if __name__ == "__main__":
    main()
