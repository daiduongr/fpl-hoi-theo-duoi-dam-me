"""
FPL Classic League Ranking Tool
================================
Lấy danh sách thành viên của một Classic League trên Fantasy Premier League,
tra cứu thành tích các mùa giải trước của từng người, rồi xếp hạng theo
rank_percentage (% thứ hạng, số càng nhỏ càng tốt) trung bình các mùa. Với
người có trên 4 mùa, chỉ 4 mùa có rank_percentage tốt nhất được xét - không
loại bớt mùa nào khỏi nhóm đó nữa.

Cách chạy:
    python fpl_league_ranking.py <league_id>

Ví dụ:
    python fpl_league_ranking.py 314
"""

import sys
import time
import requests
import pandas as pd

BASE_URL = "https://fantasy.premierleague.com/api"
REQUEST_TIMEOUT = 10          # giây, timeout cho mỗi request
REQUEST_DELAY = 0.3           # giây, delay giữa các request để tránh rate-limit


def _get_json(url: str, params: dict | None = None) -> dict | None:
    """
    Gọi GET tới `url` và trả về JSON. Xử lý lỗi cơ bản:
    - timeout
    - status code khác 200
    - lỗi kết nối / lỗi parse JSON
    Trả về None nếu có lỗi (để hàm gọi có thể xử lý gracefully).
    """
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        print(f"[LỖI] Timeout khi gọi {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[LỖI] Không thể kết nối tới {url}: {e}")
        return None

    if resp.status_code != 200:
        print(f"[LỖI] {url} trả về status code {resp.status_code}")
        return None

    try:
        return resp.json()
    except ValueError:
        print(f"[LỖI] Không parse được JSON từ {url}")
        return None


def get_league_members(league_id: int) -> pd.DataFrame:
    """
    Bước 1: Lấy toàn bộ thành viên trong 1 classic league.

    Gọi API leagues-classic/{league_id}/standings/, tự động lặp qua các
    trang (page_standings) cho tới khi has_next = False.

    Fallback: nếu "standings.results" rỗng (thường xảy ra đầu mùa giải,
    trước khi gameweek 1 được tính điểm), FPL xếp toàn bộ thành viên vào
    "new_entries" thay vì "standings". Trong trường hợp đó, tự động lấy
    danh sách từ new_entries (page_new_entries) để script vẫn chạy được.

    Trả về DataFrame với các cột: entry_id, player_name, entry_name
    """
    members = []
    page = 1
    last_data = None

    while True:
        url = f"{BASE_URL}/leagues-classic/{league_id}/standings/"
        data = _get_json(url, params={"page_standings": page})
        last_data = data if data is not None else last_data

        if data is None:
            print(f"[CẢNH BÁO] Bỏ qua trang {page} của league {league_id} do lỗi API.")
            break

        standings = data.get("standings", {})
        results = standings.get("results", [])

        for r in results:
            members.append(
                {
                    "entry_id": r.get("entry"),
                    "player_name": r.get("player_name"),
                    "entry_name": r.get("entry_name"),
                }
            )

        has_next = standings.get("has_next", False)
        print(f"  Đã lấy trang {page} ({len(results)} thành viên) - has_next={has_next}")

        if not has_next:
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    # Fallback sang new_entries nếu standings rỗng (đầu mùa giải, chưa có GW nào)
    if not members and last_data is not None and last_data.get("new_entries", {}).get("results"):
        print("  [THÔNG BÁO] 'standings' rỗng (có thể mùa giải chưa bắt đầu) "
              "- chuyển sang lấy từ 'new_entries'.")
        page = 1
        while True:
            url = f"{BASE_URL}/leagues-classic/{league_id}/standings/"
            data = _get_json(url, params={"page_new_entries": page})

            if data is None:
                print(f"[CẢNH BÁO] Bỏ qua trang {page} của new_entries do lỗi API.")
                break

            new_entries = data.get("new_entries", {})
            results = new_entries.get("results", [])

            for r in results:
                full_name = " ".join(
                    filter(None, [r.get("player_first_name"), r.get("player_last_name")])
                ) or None
                members.append(
                    {
                        "entry_id": r.get("entry"),
                        "player_name": full_name,
                        "entry_name": r.get("entry_name"),
                    }
                )

            has_next = new_entries.get("has_next", False)
            print(f"  Đã lấy trang {page} của new_entries ({len(results)} thành viên) - has_next={has_next}")

            if not has_next:
                break

            page += 1
            time.sleep(REQUEST_DELAY)

    return pd.DataFrame(members, columns=["entry_id", "player_name", "entry_name"])


def get_entry_history(entry_id: int) -> list[dict]:
    """
    Bước 2: Lấy thành tích quá khứ của 1 thành viên.

    Gọi API entry/{entry_id}/history/, trả về danh sách các mùa giải
    trong trường "past", mỗi phần tử gồm:
      - season_name
      - total_points
      - rank            (thứ hạng tổng trên toàn bộ FPL, số càng nhỏ càng tốt)
      - rank_percentage (phần trăm thứ hạng, ví dụ "2" = top 2% người chơi
                          mùa đó; số càng nhỏ càng tốt). API trả về dạng
                          chuỗi, ở đây parse sẵn sang float; nếu không parse
                          được thì để None.

    Nếu lỗi API hoặc "past" rỗng, trả về list rỗng [] (xử lý gracefully).
    """
    url = f"{BASE_URL}/entry/{entry_id}/history/"
    data = _get_json(url)

    if data is None:
        return []

    past = data.get("past", [])
    result = []
    for p in past:
        try:
            rank_percentage = float(p.get("rank_percentage"))
        except (TypeError, ValueError):
            rank_percentage = None

        result.append(
            {
                "season_name": p.get("season_name"),
                "total_points": p.get("total_points"),
                "rank": p.get("rank"),
                "rank_percentage": rank_percentage,
            }
        )
    return result


def calculate_adjusted_average(past_seasons: list[dict], max_seasons: int = 4) -> dict:
    """
    Bước 3: Tính rank_percentage (% thứ hạng) trung bình:
      1. Nếu có nhiều hơn `max_seasons` mùa -> chỉ giữ lại `max_seasons`
         mùa có rank_percentage TỐT NHẤT (số % nhỏ nhất = gần top nhất).
      2. Tính trung bình cộng rank_percentage của các mùa được giữ lại -
         KHÔNG loại thêm mùa nào khỏi nhóm này nữa.

    Input: list các dict
        {"season_name":..., "total_points":..., "rank":..., "rank_percentage":...}

    Mùa nào không có rank_percentage hợp lệ (None) sẽ không được đưa vào
    tính toán, nhưng vẫn được tính trong total_season_count.

    - Nếu không có mùa nào có rank_percentage hợp lệ -> adjusted_avg_percentage = None (N/A)
    - Nếu chỉ có 1 mùa hợp lệ (sau khi giới hạn max_seasons) -> giữ nguyên

    Trả về dict gồm:
        total_season_count      - tổng số mùa có trong lịch sử
        pool_season_count       - số mùa thực sự được xét (<= max_seasons)
        points_list             - điểm tất cả các mùa (để tham khảo)
        pool_percentages        - rank_percentage các mùa nằm trong nhóm được xét
        adjusted_avg_percentage
    """
    if not past_seasons:
        return {
            "total_season_count": 0,
            "pool_season_count": 0,
            "points_list": [],
            "pool_percentages": [],
            "adjusted_avg_percentage": None,
        }

    points_list = [s["total_points"] for s in past_seasons]
    valid_seasons = [s for s in past_seasons if s.get("rank_percentage") is not None]

    if not valid_seasons:
        return {
            "total_season_count": len(past_seasons),
            "pool_season_count": 0,
            "points_list": points_list,
            "pool_percentages": [],
            "adjusted_avg_percentage": None,
        }

    if len(valid_seasons) > max_seasons:
        # Chọn max_seasons mùa có rank_percentage TỐT nhất (nhỏ nhất), rồi
        # sắp lại theo thứ tự thời gian gốc (như trong "past") để dễ đọc.
        best_by_percentage = sorted(valid_seasons, key=lambda s: s["rank_percentage"])[:max_seasons]
        best_ids = {id(s) for s in best_by_percentage}
        pool = [s for s in valid_seasons if id(s) in best_ids]
    else:
        pool = valid_seasons

    pool_percentages = [s["rank_percentage"] for s in pool]
    adjusted_avg_percentage = sum(pool_percentages) / len(pool_percentages)

    return {
        "total_season_count": len(past_seasons),
        "pool_season_count": len(pool),
        "points_list": points_list,
        "pool_percentages": pool_percentages,
        "adjusted_avg_percentage": adjusted_avg_percentage,
    }


def build_ranking(league_id: int, max_seasons: int = 4) -> pd.DataFrame:
    """
    Kết hợp bước 1-3-4: lấy thành viên, lấy lịch sử, tính
    adjusted_avg_percentage (% thứ hạng trung bình), rồi xếp hạng TĂNG dần
    (% càng nhỏ = thành tích càng tốt, ví dụ 0.5% tốt hơn 10%).

    Với người có nhiều hơn `max_seasons` mùa trong lịch sử, chỉ `max_seasons`
    mùa có rank_percentage tốt nhất được đưa vào tính toán, không loại thêm
    mùa nào khỏi nhóm đó nữa (xem calculate_adjusted_average).

    Thành viên không có mùa quá khứ nào (adjusted_avg_percentage = N/A) VẪN
    được giữ trong bảng, xếp ở cuối.
    """
    print(f"\n=== Bước 1: Lấy danh sách thành viên của league {league_id} ===")
    members_df = get_league_members(league_id)
    print(f"Tổng số thành viên: {len(members_df)}")

    print("\n=== Bước 2-3: Lấy lịch sử & tính adjusted_avg_percentage cho từng thành viên ===")
    rows = []
    no_history = []

    for i, member in members_df.iterrows():
        entry_id = member["entry_id"]
        player_name = member["player_name"]
        entry_name = member["entry_name"]

        print(f"  ({i + 1}/{len(members_df)}) {player_name} - {entry_name} (entry_id={entry_id})")

        past_seasons = get_entry_history(entry_id)
        stats = calculate_adjusted_average(past_seasons, max_seasons=max_seasons)

        if stats["adjusted_avg_percentage"] is None:
            no_history.append(f"{player_name} ({entry_name})")

        rows.append(
            {
                "player_name": player_name,
                "entry_name": entry_name,
                "total_season_count": stats["total_season_count"],
                "seasons_used": stats["pool_season_count"],
                "points_per_season": stats["points_list"],
                "percentages_used": stats["pool_percentages"],
                "adjusted_avg_percentage": (
                    round(stats["adjusted_avg_percentage"], 2)
                    if stats["adjusted_avg_percentage"] is not None
                    else None
                ),
            }
        )

        time.sleep(REQUEST_DELAY)

    if no_history:
        print(f"\n[THÔNG BÁO] {len(no_history)} thành viên chưa có dữ liệu mùa trước "
              f"(adjusted_avg_percentage = N/A), sẽ được xếp cuối bảng:")
        for name in no_history:
            print(f"  - {name}")

    print("\n=== Bước 4: Xếp hạng theo adjusted_avg_percentage tăng dần (N/A xuống cuối) ===")
    ranking_df = pd.DataFrame(rows)

    if ranking_df.empty:
        print("[CẢNH BÁO] Không có thành viên nào để xếp hạng.")
        return ranking_df

    # ascending=True vì % thứ hạng càng nhỏ = thành tích càng tốt.
    # na_position="last" đảm bảo adjusted_avg_percentage = NaN luôn nằm cuối bảng.
    ranking_df = ranking_df.sort_values(
        "adjusted_avg_percentage", ascending=True, na_position="last"
    ).reset_index(drop=True)
    ranking_df.insert(0, "rank", ranking_df.index + 1)

    return ranking_df


def main():
    if len(sys.argv) < 2:
        print("Cách dùng: python fpl_league_ranking.py <league_id>")
        sys.exit(1)

    try:
        league_id = int(sys.argv[1])
    except ValueError:
        print("[LỖI] league_id phải là số nguyên.")
        sys.exit(1)

    ranking_df = build_ranking(league_id)

    if ranking_df.empty:
        print("\nKhông có kết quả để hiển thị.")
        return

    print("\n=== KẾT QUẢ XẾP HẠNG ===")
    with pd.option_context("display.max_rows", None, "display.max_colwidth", None, "display.width", 200):
        print(ranking_df.to_string(index=False))

    output_file = f"fpl_league_{league_id}_ranking.csv"
    ranking_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"\nĐã lưu kết quả vào: {output_file}")


if __name__ == "__main__":
    main()
