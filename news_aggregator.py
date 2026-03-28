#!/usr/bin/env python3
"""
Daily News Digest — Aggregator & Sender
Fetches RSS → Summarizes with Claude AI → Sends via Telegram
Author: Built for Leo @ MAFC Vietnam
"""

import os
import time
import feedparser
import requests
from datetime import datetime, timedelta, timezone
from anthropic import Anthropic

# ─── Configuration from Environment Variables ──────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]

MAX_ARTICLES_PER_CAT = 12
TOP_N_SUMMARY        = 5
HOURS_LOOKBACK       = 24

# ─── RSS Feed Sources ──────────────────────────────────────────────────────────
RSS_FEEDS = {
    "💰 Tài chính & Đầu tư": [
        ("VnExpress - Kinh doanh",   "https://vnexpress.net/rss/kinh-doanh.rss"),
        ("Tuổi Trẻ - Kinh tế",       "https://tuoitre.vn/rss/kinh-te.rss"),
        ("CafeF - Tài chính",        "https://cafef.vn/rss/tai-chinh-ngan-hang.rss"),
        ("CafeF - Chứng khoán",      "https://cafef.vn/rss/thi-truong-chung-khoan.rss"),
        ("CafeF - Bất động sản",     "https://cafef.vn/rss/bat-dong-san.rss"),
        ("VnEconomy - Tài chính",    "https://vneconomy.vn/tai-chinh.rss"),
        ("CafeBiz - Kinh doanh",     "https://cafebiz.vn/rss/kinh-doanh.rss"),
        ("Nhịp cầu Đầu tư",          "https://nhipcaudautu.vn/rss/"),
    ],
    "💻 Công nghệ & AI / Data": [
        ("VnExpress - Số hóa",       "https://vnexpress.net/rss/so-hoa.rss"),
        ("Tuổi Trẻ - Nhịp sống số",  "https://tuoitre.vn/rss/nhip-song-so.rss"),
        ("Tinhte.vn",                "https://tinhte.vn/rss"),
        ("GenK",                     "https://genk.vn/rss/home.rss"),
        ("ICTNews",                  "https://ictnews.vietnamnet.vn/rss"),
        ("TechCrunch",               "https://techcrunch.com/feed/"),
        ("The Verge",                "https://www.theverge.com/rss/index.xml"),
        ("Ars Technica",             "https://feeds.arstechnica.com/arstechnica/index"),
    ],
    "🌍 Tin quốc tế": [
        ("Reuters - Top News",       "https://feeds.reuters.com/reuters/topNews"),
        ("BBC World",                "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Bloomberg Markets",        "https://feeds.bloomberg.com/markets/news.rss"),
        ("Financial Times",          "https://www.ft.com/rss/home"),
        ("The Economist",            "https://www.economist.com/finance-and-economics/rss.xml"),
        ("CNBC - Markets",           "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
    ],
    "📰 Tin tức tổng hợp": [
        ("VnExpress - Tin mới",      "https://vnexpress.net/rss/tin-moi-nhat.rss"),
        ("Tuổi Trẻ - Tin mới",       "https://tuoitre.vn/rss/tin-moi-nhat.rss"),
        ("CafeBiz - Trending",       "https://cafebiz.vn/rss/trending.rss"),
        ("Vietnamnet - Thời sự",     "https://vietnamnet.vn/rss/thoi-su.rss"),
        ("Dân Trí",                  "https://dantri.com.vn/rss/home.rss"),
    ],
}


def fetch_recent_articles(feeds: list[tuple], hours: int = 24) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    for source_name, url in feeds:
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
            count = 0
            for entry in feed.entries:
                pub_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if pub_date is None or pub_date >= cutoff:
                    articles.append({
                        "source":    source_name,
                        "title":     entry.get("title", "").strip(),
                        "link":      entry.get("link", ""),
                        "summary":   entry.get("summary", "")[:300].strip(),
                        "published": pub_date.strftime("%H:%M") if pub_date else "N/A",
                    })
                    count += 1
            print(f"     ✓ {source_name}: {count} entries")
        except Exception as e:
            print(f"     ✗ {source_name}: {e}")
        time.sleep(0.3)

    seen = set()
    unique = []
    for a in articles:
        key = a["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(a)

    return unique[:MAX_ARTICLES_PER_CAT * len(feeds)]


def summarize_with_claude(category: str, articles: list[dict]) -> str:
    if not articles:
        return "_Không có bài viết mới trong 24 giờ qua._"

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    article_text = "\n".join([
        f"{i+1}. [{a['source']}] {a['title']}\n   {a['summary'][:180]}"
        for i, a in enumerate(articles[:MAX_ARTICLES_PER_CAT])
    ])

    is_intl = "quốc tế" in category.lower()

    prompt = f"""Bạn là trợ lý tóm tắt tin tức hàng ngày cho một Senior Financial Analyst và Data Analyst tại Việt Nam.

Dưới đây là các bài báo trong chủ đề "{category}" trong 24 giờ qua:

{article_text}

Nhiệm vụ:
1. Chọn TOP {TOP_N_SUMMARY} bài quan trọng và đáng đọc nhất
2. Viết tóm tắt ngắn gọn cho mỗi bài (1-2 câu tiếng Việt, súc tích, nêu rõ điểm chính)
{"3. Với bài tiếng Anh: dịch tiêu đề sang tiếng Việt, tóm tắt bằng tiếng Việt" if is_intl else "3. Ưu tiên bài có tác động đến tài chính, kinh doanh, công nghệ tại Việt Nam"}
4. Ưu tiên tin có tác động vĩ mô, thị trường tài chính, hoặc xu hướng công nghệ quan trọng

Format output (chính xác như sau, không thêm gì khác):
• [Tên nguồn] **Tiêu đề (tiếng Việt)** — Tóm tắt nội dung chính.

Chỉ trả lời danh sách tóm tắt, không có phần mở đầu hay kết luận."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=900,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text.strip()


def build_telegram_message(digests: dict) -> str:
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


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
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
        time.sleep(2)

    print("📤  Sending Telegram message...")
    send_telegram(build_telegram_message(digests))

    print(f"\n{'═'*52}")
    print(f"  ✅ All done! Digest delivered via Telegram.")
    print(f"{'═'*52}\n")


if __name__ == "__main__":
    main()
