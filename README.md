# 📋 Daily News Digest

Hệ thống tổng hợp tin tức hàng ngày tự động:
- **Fetch** RSS từ VnExpress, Tuổi Trẻ, CafeF, VnEconomy, ICTNews...
- **Tóm tắt** bằng Claude AI (tiếng Việt, súc tích)
- **Gửi** qua Telegram Bot + Gmail mỗi sáng 7:00 AM (ICT)
- **Chạy miễn phí** trên GitHub Actions

---

## 🚀 Hướng dẫn cài đặt

### Bước 1 — Tạo Telegram Bot

1. Mở Telegram → tìm **@BotFather** → gõ `/newbot`
2. Đặt tên bot (ví dụ: `Leo Daily Digest Bot`)
3. Lưu lại **Bot Token** (dạng: `123456789:ABCdef...`)
4. Chat với bot của mình 1 tin bất kỳ, sau đó truy cập:
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
5. Lấy **Chat ID** từ field `"id"` trong kết quả JSON

---

### Bước 2 — Tạo Gmail App Password

> ⚠️ Cần bật 2-Factor Authentication trước

1. Vào [myaccount.google.com/security](https://myaccount.google.com/security)
2. Tìm mục **"2-Step Verification"** → kéo xuống → **"App Passwords"**
3. Chọn app: **Mail** | device: **Other** → đặt tên "Daily Digest"
4. Google sẽ tạo **16-ký-tự mật khẩu** (ví dụ: `abcd efgh ijkl mnop`)
5. Lưu lại (bỏ dấu cách khi dùng)

---

### Bước 3 — Lấy Anthropic API Key

1. Vào [console.anthropic.com](https://console.anthropic.com)
2. **API Keys** → **Create Key** → đặt tên "Daily Digest"
3. Lưu key (dạng: `sk-ant-api03-...`)

---

### Bước 4 — Push code lên GitHub

```bash
# Clone hoặc tạo repo mới trên GitHub
git init
git add .
git commit -m "feat: daily news digest"
git remote add origin https://github.com/YOUR_USERNAME/daily-news-digest.git
git push -u origin main
```

---

### Bước 5 — Thêm GitHub Secrets

Vào repo GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Thêm 6 secrets sau:

| Secret Name | Giá trị |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token từ BotFather |
| `TELEGRAM_CHAT_ID` | Chat ID của bạn |
| `GMAIL_USER` | Email Gmail (vd: `leo@gmail.com`) |
| `GMAIL_APP_PASSWORD` | 16-ký-tự app password (không dấu cách) |
| `RECIPIENT_EMAIL` | Email nhận tin (có thể giống `GMAIL_USER`) |
| `ANTHROPIC_API_KEY` | Key từ console.anthropic.com |

---

### Bước 6 — Test thủ công

1. Vào tab **Actions** trên GitHub repo
2. Chọn workflow **"📋 Daily News Digest"**
3. Click **"Run workflow"** → **"Run workflow"**
4. Theo dõi logs — nếu thấy ✅ là thành công!

---

## ⚙️ Tùy chỉnh

### Đổi giờ gửi tin
Mở `.github/workflows/daily_digest.yml`, sửa dòng cron:
```yaml
- cron: '0 0 * * *'   # 7:00 AM ICT (UTC+7)
- cron: '30 22 * * *' # 5:30 AM ICT
- cron: '0 1 * * *'   # 8:00 AM ICT
```

### Thêm nguồn RSS
Mở `news_aggregator.py` → thêm vào dict `RSS_FEEDS`:
```python
("Tên nguồn", "https://example.com/rss.xml"),
```

### Thêm danh mục mới
```python
"🎬 Giải trí & Phim ảnh": [
    ("VnExpress - Giải trí", "https://vnexpress.net/rss/giai-tri.rss"),
    ("Tuổi Trẻ - Văn hóa",  "https://tuoitre.vn/rss/van-hoa.rss"),
],
```

---

## 🏗️ Kiến trúc

```
GitHub Actions (cron: 7AM daily)
        │
        ▼
news_aggregator.py
        │
        ├── fetch_recent_articles()  → RSS Feeds (feedparser)
        │       VnExpress, Tuổi Trẻ, CafeF, VnEconomy, ICTNews...
        │
        ├── summarize_with_claude()  → Anthropic Claude API
        │       TOP 5 bài/danh mục, tóm tắt tiếng Việt
        │
        ├── send_telegram()          → Telegram Bot API
        │       Markdown format, split 4000 chars
        │
        └── send_email()             → Gmail SMTP SSL
                HTML email đẹp, có link đọc thêm
```

---

## 💰 Chi phí ước tính

| Dịch vụ | Chi phí |
|---|---|
| GitHub Actions | **Miễn phí** (2000 phút/tháng, job này ~2-3 phút) |
| Telegram Bot | **Miễn phí** |
| Gmail SMTP | **Miễn phí** |
| Anthropic API | ~$0.01–0.03/ngày (3 API calls, claude-sonnet) |

**Tổng: ~$0.30–0.90/tháng** (chỉ tiền Claude API)

---

## 🐛 Troubleshooting

**Telegram không nhận được tin:**
- Kiểm tra Bot Token và Chat ID đúng chưa
- Đảm bảo đã nhắn tin cho bot ít nhất 1 lần

**Gmail không gửi được:**
- App Password phải bỏ dấu cách (16 ký tự liền)
- Tài khoản phải bật 2FA

**Lỗi trong GitHub Actions:**
- Click vào job bị đỏ để xem logs chi tiết
- Bot Telegram sẽ tự động nhận thông báo khi lỗi
