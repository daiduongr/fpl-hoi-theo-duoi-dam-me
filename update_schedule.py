"""
Ghi lịch chạy của workflow theo lịch thi đấu FPL: mỗi GW chưa xong có 2 lần chạy (giờ UTC),
1 giờ sau khi trận cuối kết thúc và 6 giờ sau đó (lúc FPL thường đã chốt bonus).

Workflow gọi script này sau mỗi lần chạy, nên khi trận bị đổi giờ hay hoãn, lịch tự được sửa lại.

Cách chạy:
    python update_schedule.py
"""

import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fpl_prize_page import get_json, MATCH_LENGTH

WORKFLOW = Path(__file__).parent / ".github" / "workflows" / "update.yml"
RUN_AFTER = [timedelta(hours=1), timedelta(hours=6)]
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


def cron_lines(now=None):
    now = now or datetime.now(timezone.utc)
    lines, seen = [], set()
    for gw, end in gw_ends().items():
        for i, delay in enumerate(RUN_AFTER):
            t = end + delay
            if t <= now:
                continue
            expr = f"{t.minute} {t.hour} {t.day} {t.month} *"
            if expr in seen:
                continue
            seen.add(expr)
            label = "xong" if i == 0 else "chốt bonus"
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
