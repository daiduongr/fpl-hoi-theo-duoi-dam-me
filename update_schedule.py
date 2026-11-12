"""
Ghi lịch chạy của workflow theo lịch thi đấu FPL. Mỗi GW có 3 lần chạy (giờ UTC):
1 giờ sau khi trận cuối kết thúc, 6 giờ sau đó (bonus tạm đã vào)
và 09:30 giờ Anh sáng hôm sau (từ mùa 2026/27 FPL chốt chính thức điểm, BXH lúc 09:00 giờ Anh).

Workflow gọi script này sau mỗi lần chạy, nên khi trận bị đổi giờ hay hoãn, lịch tự được sửa lại.

Cách chạy:
    python update_schedule.py
"""

import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fpl_prize_page import get_json, MATCH_LENGTH, RUN_AFTER_END

WORKFLOW = Path(__file__).parent / ".github" / "workflows" / "update.yml"
RUN_AFTER = [RUN_AFTER_END, timedelta(hours=6)]
FINALIZE_DELAY = timedelta(minutes=30)  # chạy 09:30 giờ Anh, sau mốc FPL chốt điểm 09:00
BEGIN = "# BEGIN GW SCHEDULE"
END = "# END GW SCHEDULE"
# Hết mùa: giữ 1 lần chạy đầu tháng 8 để workflow không bị rỗng lịch
OFF_SEASON = '    - cron: "17 6 1 8 *"  # ngoài mùa giải'


def gw_ends():
    fixtures = get_json("/fixtures/")
    kickoffs = {}
    for f in fixtures:
        if f["event"] and f["kickoff_time"] and not f["finished"]:
            kickoffs.setdefault(f["event"], []).append(datetime.fromisoformat(f["kickoff_time"].replace("Z", "+00:00")))
    # GW có trận chưa đá: kết thúc = trận cuối cùng của GW (kể cả trận đã đá) + thời lượng trận
    for f in fixtures:
        if f["event"] in kickoffs and f["finished"] and f["kickoff_time"]:
            kickoffs[f["event"]].append(datetime.fromisoformat(f["kickoff_time"].replace("Z", "+00:00")))
    return {gw: max(ks) + MATCH_LENGTH for gw, ks in sorted(kickoffs.items())}


def last_sunday(year, month):
    d = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def uk_offset(t):
    """Giờ Anh: BST (UTC+1) từ 01:00 UTC Chủ nhật cuối tháng 3 tới 01:00 UTC Chủ nhật cuối tháng 10."""
    start = last_sunday(t.year, 3).replace(hour=1)
    stop = last_sunday(t.year, 10).replace(hour=1)
    return timedelta(hours=1) if start <= t < stop else timedelta(0)


def after_uk_finalize(end):
    """Từ mùa 2026/27, FPL chốt chính thức điểm và BXH của GW lúc 09:00 giờ Anh.
    Trả về (giờ UTC) mốc 09:00 giờ Anh đầu tiên sau khi GW kết thúc, cộng FINALIZE_DELAY."""
    day = (end + uk_offset(end)).date()
    while True:
        t = datetime(day.year, day.month, day.day, 9, tzinfo=timezone.utc)
        t -= uk_offset(t)
        if t > end:
            return t + FINALIZE_DELAY
        day += timedelta(days=1)


def cron_lines(now=None):
    now = now or datetime.now(timezone.utc)
    runs = []
    for gw, end in gw_ends().items():
        runs += [(end + delay, gw, "xong" if i == 0 else "chốt bonus") for i, delay in enumerate(RUN_AFTER)]
        runs.append((after_uk_finalize(end), gw, "FPL chốt điểm 09:00 giờ Anh"))
    lines, seen = [], set()
    for t, gw, label in sorted(runs):
        if t <= now:
            continue
        expr = f"{t.minute} {t.hour} {t.day} {t.month} *"
        if expr in seen:
            continue
        seen.add(expr)
        lines.append(f'    - cron: "{expr}"  # GW{gw} {label}, {t:%d/%m %H:%M} UTC')
    return lines or [OFF_SEASON]


def main():
    text = WORKFLOW.read_text(encoding="utf-8")
    block = "\n".join([f"    {BEGIN} (tự sinh bởi update_schedule.py, đừng sửa tay)", *cron_lines(), f"    {END}"])
    new = re.sub(rf"    {BEGIN}.*?{END}", block, text, flags=re.S)
    if new == text:
        print("Lịch chạy không đổi")
        return
    WORKFLOW.write_text(new, encoding="utf-8")
    print(f"Đã cập nhật lịch chạy: {block.count('- cron:')} lần")


if __name__ == "__main__":
    main()
