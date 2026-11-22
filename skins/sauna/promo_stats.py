"""Замер страниц сета Sauna в Steam Workshop (без входа, публичные данные).

Пишет строку на каждую страницу в data/promo_stats.csv и печатает таблицу с приростом
к предыдущему замеру. Запуск: python -I skins/sauna/promo_stats.py
"""
import csv
import datetime as dt
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PAGES = {
    "3840348906": "Collection",
    "3840311723": "Sauna Stove",
    "3840333377": "Sauna Bench",
    "3840335380": "Sauna Chair",
    "3840337593": "Sauna Stone Box",
    "3840340102": "Sauna Changing Locker",
    "3840341829": "Sauna Towel Wrap",
    "3840344106": "Sauna Robe",
}
CSV = Path(__file__).resolve().parents[2] / "data" / "promo_stats.csv"
FIELDS = ["date", "id", "name", "visitors", "subs", "lifetime_subs", "favorites", "comments", "stars"]
UA = {"User-Agent": "Mozilla/5.0"}


def api():
    form = {"itemcount": len(PAGES)}
    for i, pid in enumerate(PAGES):
        form[f"publishedfileids[{i}]"] = pid
    req = urllib.request.Request(
        "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
        data=urllib.parse.urlencode(form).encode(), headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        items = json.load(r)["response"]["publishedfiledetails"]
    return {x["publishedfileid"]: x for x in items}


def page(pid):
    url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={pid}&l=english"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
            html = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:  # Steam отвечает 429 на частые запросы
        print(f"  {pid}: page HTTP {e.code}, comments not measured")
        return "", ""
    finally:
        time.sleep(2)
    m = re.search(r"(\d[\d,]*)(?:\s|<[^>]+>)*Comments", html)
    comments = int(m.group(1).replace(",", "")) if m else 0
    s = re.search(r"/(\d)-star_large\.png", html)
    stars = s.group(1) if s else ""
    return comments, stars


def last_rows():
    if not CSV.exists():
        return {}
    with CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {r["id"]: r for r in rows}


def main():
    prev = last_rows()
    data = api()
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for pid, name in PAGES.items():
        x = data.get(pid, {})
        comments, stars = page(pid)
        rows.append({"date": now, "id": pid, "name": name,
                     "visitors": x.get("views", 0), "subs": x.get("subscriptions", 0),
                     "lifetime_subs": x.get("lifetime_subscriptions", 0),
                     "favorites": x.get("favorited", 0), "comments": comments, "stars": stars})
    new = not CSV.exists()
    with CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)

    def d(r, k):
        p = prev.get(r["id"])
        if p and str(r[k]) != "" and p[k] != "":
            return f"{r[k]} (+{int(r[k]) - int(p[k])})"
        return str(r[k]) if r[k] != "" else "?"

    print(f"{'page':24}{'visitors':>14}{'subs':>10}{'favs':>10}{'comm':>10}  stars")
    for r in rows:
        print(f"{r['name']:24}{d(r, 'visitors'):>14}{d(r, 'subs'):>10}{d(r, 'favorites'):>10}"
              f"{d(r, 'comments'):>10}  {r['stars'] or '-'}")


if __name__ == "__main__":
    main()
