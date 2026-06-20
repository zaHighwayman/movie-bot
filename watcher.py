import os
import sys
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# ── Config ─────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
SEARCH_KEYWORD = os.getenv("SEARCH_KEYWORD", "odyssey").lower()
STATE_FILE = "notified_state.txt"

# Finnkino XML API — lists all current & upcoming movies
FINNKINO_EVENTS_URL = "https://www.finnkino.fi/xml/Events/"
FINNKINO_SCHEDULE_URL = "https://www.finnkino.fi/xml/Schedule/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/xml, text/xml, */*",
    "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.8",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    print(f"[{now()}] {msg}", flush=True)

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False}
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

# ── Finnkino XML API ───────────────────────────────────────────────────────────

def fetch_events():
    """Fetch all events from Finnkino XML API, return matches for keyword."""
    r = requests.get(FINNKINO_EVENTS_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    matches = []
    for event in root.findall(".//Event"):
        title = (event.findtext("Title") or "").strip()
        original = (event.findtext("OriginalTitle") or "").strip()
        event_id = event.findtext("ID") or ""
        rating = event.findtext("Rating") or ""
        genres = event.findtext("Genres") or ""
        synopsis = (event.findtext("Synopsis") or "")[:200]

        if SEARCH_KEYWORD in title.lower() or SEARCH_KEYWORD in original.lower():
            matches.append({
                "id": event_id,
                "title": title,
                "original": original,
                "rating": rating,
                "genres": genres,
                "synopsis": synopsis,
            })
    return matches

def fetch_showtimes(event_id: str):
    """Get the first few showtimes for an event."""
    try:
        r = requests.get(FINNKINO_SCHEDULE_URL, headers=HEADERS, params={"eventID": event_id}, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        shows = []
        for show in root.findall(".//Show"):
            shows.append({
                "theatre": show.findtext("Theatre") or "?",
                "start": (show.findtext("dttmShowStart") or "").replace("T", " "),
                "url": show.findtext("ShowURL") or "",
            })
        return shows
    except Exception as e:
        log(f"⚠️  Could not fetch showtimes for event {event_id}: {e}")
        return []

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log(f"🔍 Checking Finnkino XML API for '{SEARCH_KEYWORD}'...")
    already_notified = load_state()

    try:
        matches = fetch_events()
    except Exception as e:
        log(f"❌ Failed to fetch Finnkino events: {e}")
        sys.exit(1)

    log(f"Found {len(matches)} match(es) for '{SEARCH_KEYWORD}'.")

    if not matches:
        log("😴 Not found yet.")
        sys.exit(0)

    new_matches = [m for m in matches if m["id"] not in already_notified]

    if not new_matches:
        log("ℹ️  Already notified about all found events.")
        sys.exit(0)

    log(f"🎉 {len(new_matches)} new event(s) found! Sending notification.")

    lines = [f"🎬 <b>'{SEARCH_KEYWORD.title()}' is now on Finnkino!</b>\n"]
    for m in new_matches:
        lines.append(f"🎥 <b>{m['title']}</b>")
        if m["original"] and m["original"] != m["title"]:
            lines.append(f"   <i>{m['original']}</i>")
        if m["genres"]:
            lines.append(f"   {m['genres']}")
        if m["rating"]:
            lines.append(f"   Rated: {m['rating']}")

        shows = fetch_showtimes(m["id"])
        if shows:
            lines.append(f"\n📅 <b>First showtimes ({len(shows)} total):</b>")
            for s in shows[:4]:
                lines.append(f"  • {s['theatre']} — {s['start']}")
                if s["url"]:
                    lines.append(f"    🎟 <a href=\"{s['url']}\">Buy tickets</a>")
            if len(shows) > 4:
                lines.append(f"  … and {len(shows) - 4} more")
        else:
            lines.append("\n  (No showtimes yet — check finnkino.fi)")

        lines.append("")

    lines.append(f"👉 <a href=\"https://www.finnkino.fi\">finnkino.fi</a>")
    send_telegram("\n".join(lines))

    for m in new_matches:
        already_notified.add(m["id"])
    save_state(already_notified)

if __name__ == "__main__":
    main()
