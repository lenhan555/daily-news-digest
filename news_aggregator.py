#!/usr/bin/env python3
"""
Daily News Digest — Aggregator & Sender
Fetches RSS → Summarizes with Claude AI → Sends via Telegram & Gmail
Author: Built for Leo @ MAFC Vietnam
"""

import os
import time
import smtplib
import feedparser
import requests
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from anthropic import Anthropic

# ─── Configuration from Environment Variables ──────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL    = os.environ.get("RECIPIENT_EMAIL", GMAIL_USER)
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]

MAX_ARTICLES_PER_CAT = 10   # max articles to fetch per category
TOP_N_SUMMARY        = 5    # articles shown in digest
HOURS_LOOKBACK       = 24   # fetch articles from last N hours

# ─── RSS Feed Sources ──────────────────────────────────────────────────────────
RSS_FEEDS = {
    "💰 Tài chính & Ngân hàng": [
        ("VnExpress - Kinh doanh",  "https://vnexpress.net/rss/kinh-doanh.rss"),
        ("Tuổi Trẻ - Kinh tế",      "https://tuoitre.vn/rss/kinh-te.rss"),
        ("CafeF - Chứng khoán",     "https://cafef.vn/rss/thi-truong-chung-khoan.rss"),
        ("VnEconomy - Tài chính",   "https://vneconomy.vn/tai-chinh.rss"),
        ("Nhịp cầu Đầu tư",         "https://nhipcaudautu.vn/rss/"),
    ],
    "💻 Công nghệ & AI / Data": [
        ("VnExpress - Số hóa",      "https://vnexpress.net/rss/so-hoa.rss"),
        ("Tuổi Trẻ - Nhịp sống số", "https://tuoitre.vn/rss/nhip-song-so.rss"),
        ("ICTNews",                 "https://ictnews.vietnamnet.vn/rss"),
        ("Zing Tech",               "https://znews.vn/rss/tin-cong-nghe.rss"),
    ],
    "📰 Tin tức tổng hợp": [
        ("VnExpress - Tin mới",     "https://vnexpress.net/rss/tin-moi-nhat.rss"),
        ("Tuổi Trẻ - Tin mới",      "https://tuoitre.vn/rss/tin-moi-nhat.rss"),
        ("Vietnamnet - Thời sự",    "https://vietnamnet.vn/rss/thoi-su.rss"),
        ("Dân Trí",                 "https://dantri.com.vn/rss/home.rss"),
    ],
}


# ─── Step 1: Fetch RSS Articles ────────────────────────────────────────────────
def fetch_recent_articles(feeds: list[tuple], hours: int = 24) -> list[dict]:
    """Fetch articles from RSS feeds published within the last N hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    for source_name, url in feeds:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})

            for entry in feed.entries:
                pub_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                # Include if recent or if date is unknown (can't filter)
                if pub_date is None or pub_date >= cutoff:
                    articles.append({
                        "source":    source_name,
                        "title":     entry.get("title", "").strip(),
                        "link":      entry.get("link", ""),
                        "summary":   entry.get("summary", "")[:300].strip(),
                        "published": pub_date.strftime("%H:%M") if pub_date else "N/A",
                    })

            print(f"     ✓ {source_name}: {len(feed.entries)} entries")
        except Exception as e:
            print(f"     ✗ {source_name}: {e}")

        time.sleep(0.3)  # polite crawl delay

    # Deduplicate by title
    seen = set()
    unique = []
    for a in articles:
        key = a["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(a)

    return unique[:MAX_ARTICLES_PER_CAT * len(feeds)]


# ─── Step 2: Summarize with Claude AI ─────────────────────────────────────────
def summarize_with_claude(category: str, articles: list[dict]) -> str:
    """Use Claude to generate a concise digest for a given category."""
    if not articles:
        return "_Không có bài viết mới trong 24 giờ qua._"

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    article_text = "\n".join([
        f"{i+1}. [{a['source']}] {a['title']}\n   {a['summary'][:180]}"
        for i, a in enumerate(articles[:MAX_ARTICLES_PER_CAT])
    ])

    prompt = f"""Bạn là trợ lý tóm tắt tin tức hàng ngày cho một Senior Financial Analyst và Data Analyst tại Việt Nam.

Dưới đây là các bài báo trong chủ đề "{category}" trong 24 giờ qua:

{article_text}

Nhiệm vụ:
1. Chọn TOP {TOP_N_SUMMARY} bài quan trọng và đáng đọc nhất
2. Viết tóm tắt ngắn gọn cho mỗi bài (1-2 câu tiếng Việt, súc tích, nêu rõ điểm chính)
3. Ưu tiên bài có tác động thực tế đến tài chính, kinh doanh, hoặc công nghệ tại Việt Nam

Format output (chính xác như sau, không thêm gì khác):
• [Tên nguồn] **Tiêu đề bài** — Tóm tắt nội dung chính.

Chỉ trả lời danh sách tóm tắt, không có phần mở đầu hay kết luận."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


# ─── Step 3a: Build Telegram Message ──────────────────────────────────────────
def build_telegram_message(digests: dict) -> str:
    """Build formatted Telegram message (Markdown)."""
    today = datetime.now().strftime("%d/%m/%Y")
    day_vn = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
    weekday = day_vn[datetime.now().weekday()]

    lines = [
        f"📋 *BẢNG TIN HÀNG NGÀY*",
        f"_{weekday}, {today}_",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for category, (summary_text, articles) in digests.items():
        lines.append(f"*{category}*")
        lines.append("")
        lines.append(summary_text)

        # Top 3 links
        if articles:
            lines.append("")
            lines.append("🔗 *Đọc thêm:*")
            for a in articles[:3]:
                title = (a["title"][:55] + "…") if len(a["title"]) > 55 else a["title"]
                lines.append(f"• [{title}]({a['link']})")

        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("")

    lines.append(f"_🤖 Claude AI • {datetime.now().strftime('%H:%M')} ICT_")
    return "\n".join(lines)


# ─── Step 3b: Build Email HTML ─────────────────────────────────────────────────
def build_email_html(digests: dict) -> str:
    """Build beautiful HTML email body."""
    today = datetime.now().strftime("%d/%m/%Y")
    day_vn = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
    weekday = day_vn[datetime.now().weekday()]

    category_colors = {
        "💰 Tài chính & Ngân hàng": "#1565C0",
        "💻 Công nghệ & AI / Data": "#2E7D32",
        "📰 Tin tức tổng hợp":      "#6A1B9A",
    }

    sections_html = ""
    for category, (summary_text, articles) in digests.items():
        color   = category_colors.get(category, "#1a73e8")
        # Convert bullet points to readable HTML
        summary_html = ""
        for line in summary_text.splitlines():
            if line.startswith("•"):
                summary_html += f'<p style="margin:8px 0; padding-left:12px; border-left:3px solid {color}; line-height:1.7;">{line}</p>'
            elif line.strip():
                summary_html += f'<p style="margin:8px 0; line-height:1.7;">{line}</p>'

        links_html = "".join([
            f'<li style="margin:6px 0;">'
            f'<a href="{a["link"]}" style="color:{color}; text-decoration:none; font-size:14px;">'
            f'{a["title"][:90]}</a>'
            f'<span style="color:#999; font-size:12px; margin-left:6px;">({a["source"]})</span></li>'
            for a in articles[:5]
        ])

        sections_html += f"""
        <div style="margin-bottom:24px; border-radius:10px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.08);">
            <div style="background:{color}; padding:14px 20px;">
                <h2 style="color:#fff; margin:0; font-size:17px; font-weight:600;">{category}</h2>
            </div>
            <div style="padding:20px; background:#fff; border:1px solid #e8e8e8; border-top:none;">
                {summary_html}
                <div style="margin-top:16px; padding-top:14px; border-top:1px dashed #e0e0e0;">
                    <p style="margin:0 0 8px 0; font-weight:600; color:#555; font-size:13px;">📌 Đọc thêm</p>
                    <ul style="margin:0; padding-left:18px; list-style:none;">{links_html}</ul>
                </div>
            </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:20px; background:#f0f2f5; font-family:'Segoe UI',Arial,sans-serif; color:#333;">
    <div style="max-width:680px; margin:0 auto;">

        <!-- Header -->
        <div style="background:linear-gradient(135deg,#1a237e,#1565C0); padding:32px 28px; border-radius:12px 12px 0 0; text-align:center;">
            <div style="font-size:36px; margin-bottom:8px;">📋</div>
            <h1 style="color:#fff; margin:0; font-size:22px; font-weight:700; letter-spacing:0.5px;">Bảng Tin Hàng Ngày</h1>
            <p style="color:#90CAF9; margin:6px 0 0; font-size:14px;">{weekday}, {today}</p>
        </div>

        <!-- Body -->
        <div style="padding:24px 0; background:#f0f2f5;">
            {sections_html}
        </div>

        <!-- Footer -->
        <div style="background:#fff; border-radius:0 0 12px 12px; border:1px solid #e8e8e8;
                    padding:16px; text-align:center;">
            <p style="margin:0; color:#999; font-size:12px;">
                🤖 Tóm tắt bởi Claude AI &nbsp;•&nbsp; Gửi tự động lúc {datetime.now().strftime("%H:%M")} ICT<br>
                Hủy đăng ký: xóa secret <code>RECIPIENT_EMAIL</code> trên GitHub Actions
            </p>
        </div>

    </div>
</body>
</html>"""


# ─── Step 4: Send Functions ────────────────────────────────────────────────────
def send_telegram(message: str):
    """Send message via Telegram Bot API (handles 4096-char limit)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Split into chunks of 4000 chars (Telegram limit is 4096)
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
    for i, chunk in enumerate(chunks):
        resp = requests.post(url, json={
            "chat_id":                  TELEGRAM_CHAT_ID,
            "text":                     chunk,
            "parse_mode":               "Markdown",
            "disable_web_page_preview": True,
        }, timeout=15)
        resp.raise_for_status()
        print(f"     ✓ Telegram chunk {i+1}/{len(chunks)} sent ({len(chunk)} chars)")
        time.sleep(1)


def send_email(html_body: str):
    """Send HTML email via Gmail SMTP (SSL)."""
    today = datetime.now().strftime("%d/%m/%Y")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📋 Bảng Tin Hàng Ngày — {today}"
    msg["From"]    = f"Daily Digest <{GMAIL_USER}>"
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())

    print(f"     ✓ Email sent to {RECIPIENT_EMAIL}")


# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'═'*52}")
    print(f"  Daily News Digest — {datetime.now().strftime('%d/%m/%Y %H:%M ICT')}")
    print(f"{'═'*52}\n")

    digests = {}

    for category, feeds in RSS_FEEDS.items():
        print(f"📥  Fetching: {category}")
        articles = fetch_recent_articles(feeds, hours=HOURS_LOOKBACK)
        print(f"    → {len(articles)} unique articles found")

        print(f"🤖  Summarizing with Claude...")
        summary = summarize_with_claude(category, articles)
        digests[category] = (summary, articles)

        print(f"    → Done\n")
        time.sleep(2)  # respect API rate limits

    print("📤  Sending Telegram message...")
    send_telegram(build_telegram_message(digests))

    print("\n📧  Sending Email...")
    send_email(build_email_html(digests))

    print(f"\n{'═'*52}")
    print(f"  ✅ All done! Digest delivered successfully.")
    print(f"{'═'*52}\n")


if __name__ == "__main__":
    main()
