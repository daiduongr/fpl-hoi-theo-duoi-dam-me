# Hội theo đuổi đam mê – sổ tiền thưởng FPL

Trang tính tiền thưởng cho league Fantasy Premier League [141084](https://fantasy.premierleague.com/leagues/141084/standings/c) mùa 2026/27.

Xem trang: https://daiduongr.github.io/fpl-hoi-theo-duoi-dam-me/

## Tự cập nhật

Workflow [`update.yml`](.github/workflows/update.yml) chạy mỗi giờ. Script chỉ build lại khi có GW vừa đá xong
(mọi trận trong GW đã kết thúc) hoặc khi FPL vừa chốt bonus cho GW đó; trạng thái lưu ở `state.json`.
Vì vậy trang cập nhật khoảng 1 giờ sau trận cuối của mỗi GW, kể cả khi lịch bị dời.

Muốn build lại ngay: tab **Actions → Cập nhật sau mỗi GW → Run workflow**, chọn `force`.

Chạy tay ở máy:

```bash
python fpl_prize_page.py          # league mặc định 141084
```

Script lấy dữ liệu từ API công khai của FPL, tính thưởng theo luật của nhóm (tuần, tháng, lượt đi/về, cả mùa, bounty…) và ghi ra `index.html` từ `prize_template.html`. Không cần thư viện ngoài.
