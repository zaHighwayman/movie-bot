import os
import sys
import requests
import re
from datetime import datetime

# ── Config from environment variables ─────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
SEARCH_KEYWORD = os.getenv("SEARCH_KEYWORD", "odyssey").lower()
# File to persist already-notified URLs across runs (via GitHub Actions cache)
STATE_FILE = "notified_state.txt"

FINNKINO_URLS = [
    "https://www.finnkino.fi/en/movies/now-in-theatres/",
    "https://www.finnkino.fi/en/movies/coming-soon/",
    "https://www.finnkino.fi/en/events/",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.8",
    "Referer": "https://www.finnkino.fi/",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    print(f"[{now()}] {msg}", flush=True)

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    r = requests.post(url, json=payload, timeout=10)
    if not r.ok:
        log(f"❌ Telegram error {r.status_code}: {r.text}")
        r.raise_for_status()
    log("✅ Telegram message sent.")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_state(notified: set):
    with open(STATE_FILE, "w") as f:
        for entry in sorted(notified):
            f.write(entry + "\n")

# ── Finnkino scraping ──────────────────────────────────────────────────────────

def check_page(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        html = r.text

        found = []
        patterns = [
            r'<a[^>]+title=["\']([^"\']*' + re.escape(SEARCH_KEYWORD) + r'[^"\']*)["\'][^>]*href=["\']([^"\']+)["\']',
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]+title=["\']([^"\']*' + re.escape(SEARCH_KEYWORD) + r'[^"\']*)["\']',
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]*' + re.escape(SEARCH_KEYWORD) + r'[^<]*)\s*</a>',
        ]

        for pat in patterns:
            for m in re.finditer(pat, html, re.IGNORECASE):
                groups = m.groups()
                if len(groups) == 2:
                    if groups[0].startswith("http") or groups[0].startswith("/"):
                        href, title = groups[0], groups[1]
                    else:
                        title, href = groups[0], groups[1]
                    title = title.strip()
                    if not href.startswith("http"):
                        href = "https://www.finnkino.fi" + href
                    entry = (title, href)
                    if entry not in found:
                        found.append(entry)

        text_only = re.sub(r'<[^>]+>', ' ', html)
        keyword_present = SEARCH_KEYWORD in text_only.lower()

        return found, keyword_present, r.status_code

    except Exception as e:
        log(f"⚠️  Error fetching {url}: {e}")
        return [], False, None

def check_finnkino():
    all_matches = []
    keyword_seen = False
    for url in FINNKINO_URLS:
        matches, seen, status = check_page(url)
        log(f"Checked {url} → status={status}, matches={len(matches)}, keyword_seen={seen}")
        all_matches.extend(matches)
        if seen:
            keyword_seen = True

    seen_urls = set()
    deduped = []
    for title, href in all_matches:
        if href not in seen_urls:
            seen_urls.add(href)
            deduped.append((title, href))

    return deduped, keyword_seen

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log(f"🔍 Checking Finnkino for '{SEARCH_KEYWORD}'...")
    already_notified = load_state()

    matches, keyword_seen = check_finnkino()

    if not keyword_seen and not matches:
        log("😴 Not found yet.")
        sys.exit(0)

    new_matches = [(t, u) for t, u in matches if u not in already_notified]
    keyword_placeholder = "__keyword_seen__"

    if new_matches or (keyword_seen and keyword_placeholder not in already_notified and not matches):
        log(f"🎉 Found! Sending notification.")

        lines = [f"🎬 <b>'{SEARCH_KEYWORD.title()}' spotted on Finnkino!</b>\n"]
        if new_matches:
            for title, href in new_matches:
                lines.append(f"🎥 <b>{title}</b>")
                lines.append(f"🎟 <a href=\"{href}\">View / Buy tickets</a>\n")
        else:
            lines.append("The keyword was found on Finnkino — no direct link extracted.")
            lines.append(f"👉 <a href=\"https://www.finnkino.fi\">Check finnkino.fi</a>")

        send_telegram("\n".join(lines))

        for _, u in new_matches:
            already_notified.add(u)
        if keyword_seen and not matches:
            already_notified.add(keyword_placeholder)

        save_state(already_notified)
    else:
        log("ℹ️  Already notified about everything found.")

if __name__ == "__main__":
    main()
