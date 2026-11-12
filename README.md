# Hội theo đuổi đam mê – sổ tiền thưởng FPL

Trang tính tiền thưởng cho league Fantasy Premier League [141084](https://fantasy.premierleague.com/leagues/141084/standings/c) mùa 2026/27.

Xem trang: https://daiduongr.github.io/fpl-hoi-theo-duoi-dam-me/

## Trạng thái hiện tại (11/11/2026)

- Trang đang chạy, đã chốt đến GW10. Tự cập nhật 3 lần mỗi GW (đã bỏ lần chạy 1 ngày trước deadline từ 11/11/2026).
- 💸 hiện cạnh người có tổng thưởng (realized + unrealized) thấp nhất.
- Còn thiếu: secret `WORKFLOW_TOKEN`, nên khi FPL đổi giờ đá, lịch chạy không tự sửa được; phải chạy `python update_schedule.py` ở máy rồi push.

## Tự cập nhật

Workflow [`update.yml`](.github/workflows/update.yml) chạy 3 lần mỗi GW: 1 giờ sau trận cuối của GW, 6 giờ sau đó để lấy bonus, và 09:30 giờ Anh sáng
hôm sau (từ mùa 2026/27, FPL chốt chính thức điểm và BXH của GW lúc 09:00 giờ Anh). Thêm 2 lần dự phòng mỗi ngày (01:17, 13:17 UTC) phòng khi GitHub bỏ lịch. Lịch chạy do [`update_schedule.py`](update_schedule.py) sinh từ
lịch thi đấu FPL. Mỗi lần chạy, workflow tính lại lịch; nếu trận bị đổi giờ hay hoãn, nó tự sửa lịch và push.
Bước này cần secret `WORKFLOW_TOKEN` (fine-grained token, repo này, quyền *Contents* và *Workflows*: Read and write).

Script chỉ build lại trang khi có GW vừa đá xong hoặc FPL vừa chốt bonus; trạng thái lưu ở `state.json`.

Muốn build lại ngay: tab **Actions → Cập nhật sau mỗi GW → Run workflow**, chọn `force`.

Chạy tay ở máy:

```bash
python fpl_prize_page.py          # league mặc định 141084
```

Script lấy dữ liệu từ API công khai của FPL, tính thưởng theo luật của nhóm (tuần, tháng, lượt đi/về, cả mùa, bounty…) và ghi ra `index.html` từ `prize_template.html`. Không cần thư viện ngoài.
