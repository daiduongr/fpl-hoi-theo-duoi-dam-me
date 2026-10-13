# Hội theo đuổi đam mê – sổ tiền thưởng FPL

Trang tính tiền thưởng cho league Fantasy Premier League [141084](https://fantasy.premierleague.com/leagues/141084/standings/c) mùa 2026/27.

Xem trang: https://daiduongr.github.io/fpl-hoi-theo-duoi-dam-me/

## Tự cập nhật

Workflow [`update.yml`](.github/workflows/update.yml) chạy 3 lần mỗi GW: 1 ngày trước deadline (cập nhật giá trị
đội, hạng overall trước khi chốt đội), 1 giờ sau trận cuối của GW, và 6 giờ sau đó để lấy bonus đã chốt. Lịch chạy do [`update_schedule.py`](update_schedule.py) sinh từ
lịch thi đấu FPL. Mỗi lần chạy, workflow tính lại lịch; nếu trận bị đổi giờ hay hoãn, nó tự sửa lịch và push.
Bước này cần secret `WORKFLOW_TOKEN` (fine-grained token, repo này, quyền *Contents* và *Workflows*: Read and write).

Script chỉ build lại trang khi có GW vừa đá xong, FPL vừa chốt bonus, hoặc vừa tới mốc 1 ngày trước deadline; trạng thái lưu ở `state.json`.

Muốn build lại ngay: tab **Actions → Cập nhật sau mỗi GW → Run workflow**, chọn `force`.

Chạy tay ở máy:

```bash
python fpl_prize_page.py          # league mặc định 141084
```

Script lấy dữ liệu từ API công khai của FPL, tính thưởng theo luật của nhóm (tuần, tháng, lượt đi/về, cả mùa, bounty…) và ghi ra `index.html` từ `prize_template.html`. Không cần thư viện ngoài.
