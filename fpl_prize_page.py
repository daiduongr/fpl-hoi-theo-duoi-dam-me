"""
Tính tiền thưởng league "Hội theo đuổi đam mê" theo luật trong file
"Hội thôi đuổi đam mê - FPL .xlsx", lấy dữ liệu trực tiếp từ API FPL,
rồi xuất ra trang index.html (GitHub Pages).

Cách chạy:
    python fpl_prize_page.py                 # league mặc định 141084
    python fpl_prize_page.py <league_id>
    python fpl_prize_page.py --if-changed    # chỉ build khi có GW vừa xong hoặc vừa chốt bonus
"""

import json
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE_URL = "https://fantasy.premierleague.com/api"
HERE = Path(__file__).parent
TEMPLATE = HERE / "prize_template.html"
OUTPUT = HERE / "index.html"
STATE = HERE / "state.json"   # GW đã build gần nhất, dùng cho --if-changed
MATCH_LENGTH = timedelta(hours=2)
HEAD = ('<!doctype html>\n<html lang="vi">\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')

# Biệt danh trong file Excel, ghép theo entry id (khớp điểm từng GW)
NICKNAMES = {
    4300857: "Hiếu Lê", 3179102: "Tuấn", 1046607: "Hinh", 3187181: "Toàn",
    229859: "Dương", 3179617: "Hải", 439704: "Trung", 443742: "Hoàng",
    3179539: "Bàng",
}

# Luật chia thưởng (đơn vị: nghìn đồng), lấy từ sheet dashboard
WEEK_PRIZES = [100, 30, 15]
MONTH_PRIZES = [50, 25, 10]
HALF_PRIZES = [300, 150, 60]
SEASON_PRIZES = [500, 250, 120]
CUP_PRIZES = [150, 75]
TEAM_VALUE_PRIZE = 150
HIGH_WEEK_PRIZE = 150
BOUNTY_PER_PLAYER = 50
BOUNTY_RANK = 500_000
BUY_IN_FIRST = 550   # đóng đầu mùa (gồm 50 bounty)
BUY_IN_SECOND = 500  # đóng lượt về, trừ đi tiền đã thắng lượt đi
FIRST_HALF = range(1, 20)
SECOND_HALF = range(20, 39)
MONTH_VN = {
    "August": "Tháng 8", "September": "Tháng 9", "October": "Tháng 10",
    "November": "Tháng 11", "December": "Tháng 12", "January": "Tháng 1",
    "February": "Tháng 2", "March": "Tháng 3", "April": "Tháng 4", "May": "Tháng 5",
}


def get_json(path):
    req = urllib.request.Request(f"{BASE_URL}{path}", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def split_prizes(scores, prizes):
    """Chia thưởng theo hạng; người đồng hạng chia đều tổng giải của các vị trí họ chiếm."""
    ordered = sorted(scores.items(), key=lambda kv: -kv[1])
    result = {pid: 0.0 for pid in scores}
    pos = 0
    while pos < len(ordered):
        tied = [pid for pid, s in ordered if s == ordered[pos][1]]
        pool = sum(prizes[pos:pos + len(tied)])
        for pid in tied:
            result[pid] = pool / len(tied)
        pos += len(tied)
    return result


def ranks(scores):
    return {pid: 1 + sum(1 for s in scores.values() if s > v) for pid, v in scores.items()}


def main(league_id, if_changed=False):
    boot = get_json("/bootstrap-static/")
    events = {e["id"]: e for e in boot["events"]}
    played = [e["id"] for e in boot["events"] if e["finished"] or e["is_current"]]
    # FPL bật cờ finished muộn (sau khi chốt bonus); coi GW đã xong khi mọi trận đã đá xong
    fixtures = get_json("/fixtures/")
    finished = {e["id"] for e in boot["events"] if e["finished"]} | {
        g for g in played
        if all(f["finished"] or f["finished_provisional"] for f in fixtures if f["event"] == g)}

    # Chỉ build lại khi có GW mới đá xong, hoặc FPL vừa chốt bonus (data_checked) cho GW đó
    last_done = max(finished, default=0)
    state = {"league": league_id, "finished_gw": last_done,
             "data_checked": bool(last_done and events[last_done]["data_checked"])}
    if if_changed and STATE.exists() and json.loads(STATE.read_text()) == state:
        print(f"Không có gì mới (đã build GW{last_done}, data_checked={state['data_checked']})")
        return

    # Lần cập nhật tới = giờ đá trận cuối của GW tiếp theo + 2 tiếng + 1 tiếng (khớp update_schedule.py)
    kickoffs = {}
    for f in fixtures:
        if f["event"] and f["kickoff_time"]:
            kickoffs.setdefault(f["event"], []).append(datetime.fromisoformat(f["kickoff_time"].replace("Z", "+00:00")))
    next_gw = next((g for g in sorted(kickoffs) if g not in finished), None)
    next_update = {"gw": next_gw, "eta": (max(kickoffs[next_gw]) + MATCH_LENGTH + timedelta(hours=1)).isoformat()} if next_gw else None

    league = get_json(f"/leagues-classic/{league_id}/standings/")

    players = []
    for row in league["standings"]["results"]:
        pid = row["entry"]
        hist = get_json(f"/entry/{pid}/history/")
        entry = get_json(f"/entry/{pid}/")
        gw = {c["event"]: c["points"] - c["event_transfers_cost"] for c in hist["current"]}
        last = hist["current"][-1] if hist["current"] else {"value": 1000, "bank": 0}
        players.append({
            "id": pid,
            "nick": NICKNAMES.get(pid, row["player_name"]),
            "name": row["player_name"],
            "team": row["entry_name"],
            "gw": gw,
            "total": row["total"],
            "overall_rank": entry.get("summary_overall_rank"),
            "value": last["value"] / 10,
            "bank": last["bank"] / 10,
        })
    ids = [p["id"] for p in players]
    by_id = {p["id"]: p for p in players}
    # Mỗi khoản thưởng: realized (đã chốt) hoặc unrealized (tạm tính theo thứ hạng hiện tại)
    money = {pid: {"realized": {}, "unrealized": {}, "first_half_realized": 0.0,
                   "first_half_unrealized": 0.0} for pid in ids}
    season_done = 38 in finished

    def add(prizes, cat, realized, first_half):
        for pid, amt in prizes.items():
            if not amt:
                continue
            m = money[pid]
            bucket = m["realized" if realized else "unrealized"]
            bucket[cat] = bucket.get(cat, 0.0) + amt
            if first_half:
                m["first_half_realized" if realized else "first_half_unrealized"] += amt

    # Giải tuần
    weeks = []
    for g in played:
        scores = {pid: by_id[pid]["gw"].get(g, 0) for pid in ids}
        prize = split_prizes(scores, WEEK_PRIZES)
        done = g in finished
        add(prize, "week", done, g in FIRST_HALF)
        weeks.append({"gw": g, "finished": done, "scores": scores, "prizes": prize,
                      "rank": ranks(scores)})

    # Giải tháng, theo các phase chính thức của FPL
    months = []
    for ph in boot["phases"]:
        if ph["name"] == "Overall":
            continue
        gws = range(ph["start_event"], ph["stop_event"] + 1)
        started = any(g in played for g in gws)
        done = all(g in finished for g in gws)
        totals = {pid: sum(by_id[pid]["gw"].get(g, 0) for g in gws) for pid in ids} if started else {}
        prize = split_prizes(totals, MONTH_PRIZES) if started else {}
        add(prize, "month", done, ph["stop_event"] in FIRST_HALF)
        months.append({
            "name": MONTH_VN.get(ph["name"], ph["name"]),
            "start": ph["start_event"], "stop": ph["stop_event"],
            "status": "done" if done else ("live" if started else "upcoming"),
            "totals": totals, "prizes": prize, "rank": ranks(totals) if totals else {},
        })

    # Giải lượt đi / lượt về / cả mùa
    def race(gws, prizes, cat, first_half):
        totals = {pid: sum(by_id[pid]["gw"].get(g, 0) for g in gws) for pid in ids}
        started = any(g in played for g in gws)
        prize = split_prizes(totals, prizes) if started else {}
        add(prize, cat, gws[-1] in finished, first_half)
        return {"totals": totals, "rank": ranks(totals), "prizes": prize, "started": started}

    races = {
        "first_half": race(FIRST_HALF, HALF_PRIZES, "half1", True),
        "second_half": race(SECOND_HALF, HALF_PRIZES, "half2", False),
        "season": race(range(1, 39), SEASON_PRIZES, "season", False),
    }

    # Giá trị đội cao nhất, điểm tuần cao nhất: chốt cuối mùa
    values = {pid: by_id[pid]["value"] for pid in ids}
    value_prize = split_prizes(values, [TEAM_VALUE_PRIZE])
    add(value_prize, "team_value", season_done, False)
    best_week = {pid: max((by_id[pid]["gw"].get(g, 0) for g in played), default=0) for pid in ids}
    high_prize = split_prizes(best_week, [HIGH_WEEK_PRIZE])
    add(high_prize, "high_week", season_done, False)
    high_week = max(((by_id[pid]["gw"].get(g, 0), pid, g) for pid in ids for g in played), default=None)

    # Bounty: hạng overall < 500K, quỹ chia đều cho những người đạt
    qualified = [pid for pid in ids if (by_id[pid]["overall_rank"] or 10**9) < BOUNTY_RANK]
    bounty_pool = BOUNTY_PER_PLAYER * len(ids)
    add({pid: bounty_pool / len(qualified) for pid in qualified}, "bounty", season_done, False)

    rows = []
    for pid in ids:
        m = money[pid]
        realized = sum(m["realized"].values())
        unrealized = sum(m["unrealized"].values())
        rows.append({
            "id": pid, **m, "realized_total": realized, "unrealized_total": unrealized,
            "second_payment": BUY_IN_SECOND - m["first_half_realized"],
            "second_payment_projected": BUY_IN_SECOND - m["first_half_realized"] - m["first_half_unrealized"],
            "net": realized - BUY_IN_FIRST - BUY_IN_SECOND,
        })

    now = datetime.now(timezone(timedelta(hours=7)))
    current = next((e["id"] for e in boot["events"] if e["is_current"]), None)
    data = {
        "league": {"id": league_id, "name": league["league"]["name"]},
        "updated": now.strftime("%H:%M, %d/%m/%Y"),
        "current_gw": current,
        "current_finished": current in finished,
        "next_update": next_update,
        "bonus_confirmed": state["data_checked"],
        "next_deadline": next((e["deadline_time"] for e in boot["events"] if e["is_next"]), None),
        "players": [{k: v for k, v in p.items() if k != "gw"} | {"gw": {str(k): v for k, v in p["gw"].items()}}
                    for p in players],
        "weeks": weeks,
        "months": months,
        "money": rows,
        "races": races,
        "value_prizes": value_prize,
        "high_week_prizes": high_prize,
        "high_week": {"points": high_week[0], "id": high_week[1], "gw": high_week[2]} if high_week else None,
        "bounty": {"pool": bounty_pool, "qualified": qualified, "threshold": BOUNTY_RANK},
        "rules": {
            "week": WEEK_PRIZES, "month": MONTH_PRIZES, "half": HALF_PRIZES, "season": SEASON_PRIZES,
            "cup": CUP_PRIZES, "team_value": TEAM_VALUE_PRIZE, "high_week": HIGH_WEEK_PRIZE,
            "bounty": BOUNTY_PER_PLAYER, "buy_in_first": BUY_IN_FIRST, "buy_in_second": BUY_IN_SECOND,
        },
    }
    html = TEMPLATE.read_text(encoding="utf-8").replace(
        "/*__DATA__*/null", json.dumps(data, ensure_ascii=False, default=str))
    OUTPUT.write_text(HEAD + html, encoding="utf-8")
    STATE.write_text(json.dumps(state) + "\n")
    print(f"Đã ghi {OUTPUT} (GW hiện tại: {current})")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(int(args[0]) if args else 141084, if_changed="--if-changed" in sys.argv)
