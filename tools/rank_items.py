"""Rank Rust Workshop items by chance of acceptance and sales.

Reads data/scmm_items.json and data/workshop.json (see fetch_data.py),
writes data/item-ranking.csv and prints the table.

Metrics per item (last 12 months, Twitch Drops excluded - those are invited artists):
  subs_12m     - Workshop submissions
  store_12m    - skins accepted into the store
  one_in       - subs_12m / store_12m: roughly "one of N submissions gets accepted"
  sold_median  - median copies of a store skin for that item (accepted 1-3 years ago, so sales have settled)
  price_median - median store price, USD
  value        - store_12m / subs_12m * sold_median * price_median: relative expected gross per submission
"""
import csv
import json
import re
import statistics as st
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

# Workshop tag -> SCMM itemType where names differ
ALIAS = {
    "AK47": "Assault Rifle", "Bolt Rifle": "Bolt Action Rifle", "Mp5": "MP5A4", "Sword": "Salvaged Sword",
    "Python": "Python Revolver", "L96": "L96 Rifle", "M39": "M39 Rifle", "BBQ": "Barbeque",
    "Bandana": "Bandana Mask", "Balaclava": "Improvised Balaclava", "Burlap Pants": "Burlap Trousers",
    "Cap": "Baseball Cap", "Collared Shirt": "Shirt", "Hide Shirt": "Hide Vest", "Hide Shoes": "Hide Boots",
    "Long TShirt": "Longsleeve T-Shirt", "TShirt": "T-Shirt", "Miner Hat": "Miners Hat",
    "Roadsign Vest": "Road Sign Jacket", "Roadsign Pants": "Road Sign Kilt", "Vagabond Jacket": "Jacket",
    "Work Boots": "Boots", "Wooden Double Door": "Wood Double Door", "Bearskin Rug": "Bear Skin Rug",
}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def main():
    skins = json.loads((DATA / "scmm_items.json").read_text(encoding="utf8"))
    workshop = json.loads((DATA / "workshop.json").read_text(encoding="utf8"))
    now = datetime.now(timezone.utc)
    y1 = (now - timedelta(days=365)).strftime("%Y-%m-%d")
    y3 = (now - timedelta(days=3 * 365)).strftime("%Y-%m-%d")

    by_type = defaultdict(list)
    for s in skins:
        if s["storePriceUsd"] and not s["isTwitchDrop"] and s["timeAccepted"]:
            by_type[norm(s["itemType"])].append(s)

    rows = []
    for tag, w in workshop.items():
        store = by_type.get(norm(ALIAS.get(tag, tag)), [])
        if not store or not w["last_12m"]:
            continue
        recent = [s for s in store if s["timeAccepted"] >= y1]
        settled = [s for s in store if y3 <= s["timeAccepted"] < y1]
        if len(settled) < 3:  # too few older skins (new item): fall back to everything we have
            settled = [s for s in store if s["timeAccepted"] >= y3]
        if not settled:
            continue
        sold = st.median(s["supplyTotalEstimated"] or 0 for s in settled)
        price = st.median(s["storePriceUsd"] for s in settled) / 100
        rate = len(recent) / w["last_12m"]
        rows.append({
            "item": tag, "group": w["group"], "subs_total": w["total"], "subs_12m": w["last_12m"],
            "store_total": len(store), "store_12m": len(recent),
            "one_in": round(1 / rate, 1) if rate else None,
            "sold_median": round(sold), "price_median": price,
            "glow_share_12m": round(sum(bool(s["hasGlow"]) for s in recent) / len(recent), 2) if recent else None,
            "value": round(rate * sold * price),
        })
    rows.sort(key=lambda r: -r["value"])

    with open(DATA / "item-ranking.csv", "w", newline="", encoding="utf8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)

    print(f"{'item':24}{'subs12m':>8}{'acc12m':>7}{'1 in':>6}{'sold':>7}{'$':>6}{'glow':>6}{'value':>7}")
    for r in rows:
        print(f"{r['item'][:23]:24}{r['subs_12m']:8}{r['store_12m']:7}{r['one_in'] or 0:6.0f}"
              f"{r['sold_median']:7}{r['price_median']:6.2f}{r['glow_share_12m'] or 0:6.2f}{r['value']:7}")


if __name__ == "__main__":
    main()
