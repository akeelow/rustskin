"""Collect data for choosing which Rust item to skin.

Writes into data/:
  scmm_items.json   - every accepted Rust skin from api.scmm.app (type, accept date, copies, price)
  workshop.json     - per Workshop item tag: total submissions and submissions in the last 12 months

Usage: python tools/fetch_data.py [--skip-scmm] [--skip-workshop]
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

APPID = 252490
DATA = Path(__file__).resolve().parent.parent / "data"
UA = {"User-Agent": "rustskin-research"}
SCMM_FIELDS = [
    "name", "itemType", "itemCollection", "timeCreated", "timeAccepted",
    "supplyTotalEstimated", "storePriceUsd", "isTwitchDrop", "isPublisherDrop",
    "isLootCrateDrop", "isPermanent", "hasGlow", "hasCutout", "creatorName",
]


def http(url):
    for attempt in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read().decode("utf8")
        except Exception as e:
            print("retry", url, e, file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(url)


def fetch_scmm():
    items, page = [], 1
    while True:
        d = json.loads(http(f"https://api.scmm.app/api/item?page={page}&pageSize=100"))
        items += [{k: i.get(k) for k in SCMM_FIELDS} for i in d["items"]]
        if not d["items"] or page * 100 >= d["total"]:
            break
        page += 1
        time.sleep(0.8)  # API limit is 100 req/min
    (DATA / "scmm_items.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf8")
    print("scmm items:", len(items))


def workshop_page(tag, page):
    """Return (total_count, [time_created...]) for one browse page, newest first."""
    q = {"appid": APPID, "requiredtags[]": tag, "section": "mtxitems", "browsesort": "mostrecent", "p": page}
    s = http("https://steamcommunity.com/workshop/browse/?" + urllib.parse.urlencode(q)).replace('\\"', '"')
    i = s.find('"total_count":')
    j = s.find('"results":', i)
    seg = s[j:s.find('"next_cursor"', j)]
    times = {}
    for m in re.finditer(r'"publishedfileid":"(\d+)","[^{}]*?"time_created":(\d+)', seg):
        times.setdefault(m.group(1), int(m.group(2)))
    return int(re.match(r'"total_count":(\d+)', s[i:]).group(1)), list(times.values())


def workshop_tags():
    s = http(f"https://steamcommunity.com/workshop/browse/?appid={APPID}").replace('\\"', '"')
    i = s.find('"declaredTags":') + len('"declaredTags":')
    declared, _ = json.JSONDecoder().raw_decode(s[i:])
    return [(g["name"], t["name"]) for g in declared["mtx_tags"] for t in g["tags"]]


def count_recent(tag, cutoff):
    total, ts = workshop_page(tag, 1)
    if not ts or min(ts) < cutoff:
        return total, sum(t >= cutoff for t in ts)
    lo, hi = 1, (total + 29) // 30  # binary search for the first page holding an older item
    while lo < hi:
        mid = (lo + hi) // 2
        _, ts = workshop_page(tag, mid)
        time.sleep(0.4)
        if ts and min(ts) < cutoff:
            hi = mid
        else:
            lo = mid + 1
    _, ts = workshop_page(tag, lo)
    return total, (lo - 1) * 30 + sum(t >= cutoff for t in ts)


def fetch_workshop():
    cutoff = int((datetime.now(timezone.utc) - timedelta(days=365)).timestamp())
    out = {}
    for group, tag in workshop_tags():
        total, recent = count_recent(tag, cutoff)
        out[tag] = {"group": group, "total": total, "last_12m": recent}
        print(f"{group} | {tag}: total={total} last_12m={recent}", flush=True)
        time.sleep(0.4)
    (DATA / "workshop.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf8")


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    if "--skip-scmm" not in sys.argv:
        fetch_scmm()
    if "--skip-workshop" not in sys.argv:
        fetch_workshop()
