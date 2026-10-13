# Hội theo đuổi đam mê – sổ tiền thưởng FPL

Trang tính tiền thưởng cho league Fantasy Premier League [141084](https://fantasy.premierleague.com/leagues/141084/standings/c) mùa 2026/27.

Xem trang: https://daiduongr.github.io/fpl-hoi-theo-duoi-dam-me/

## Cập nhật

```bash
python fpl_prize_page.py          # league mặc định 141084
git commit -am "Cập nhật GW" && git push
```

Script lấy dữ liệu từ API công khai của FPL, tính thưởng theo luật của nhóm (tuần, tháng, lượt đi/về, cả mùa, bounty…) và ghi ra `index.html` từ `prize_template.html`. Không cần thư viện ngoài.
