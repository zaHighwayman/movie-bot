import os
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# ── Config from environment variables ─────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "600"))  # default 10 min

# Finnkino Events API — lists all upcoming/now-showing movies
FINNKINO_EVENTS_URL = "https://www.finnkino.fi/xml/Events/"
# Finnkino Schedule API — lists actual showtimes (used once movie is found)
FINNKINO_SCHEDULE_URL = "https://www.finnkino.fi/xml/Schedule/"

SEARCH_KEYWORD = "odyssey"

# ── Telegram helpers ───────────────────────────────────────────────────────────

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        print(f"[{now()}] ✅ Telegram message sent.")
    except Exception as e:
        print(f"[{now()}] ❌ Failed to send Telegram message: {e}")


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Finnkino polling ───────────────────────────────────────────────────────────

def fetch_events():
    """Fetch all events (movies) from Finnkino and return those matching Odyssey."""
    try:
        r = requests.get(FINNKINO_EVENTS_URL, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        matches = []
        for event in root.findall(".//Event"):
            title_el = event.find("Title")
            original_title_el = event.find("OriginalTitle")
            event_id_el = event.find("ID")
            if title_el is None:
                continue
            title = title_el.text or ""
            original_title = original_title_el.text if original_title_el is not None else ""
            if SEARCH_KEYWORD in title.lower() or SEARCH_KEYWORD in (original_title or "").lower():
                matches.append({
                    "id": event_id_el.text if event_id_el is not None else "?",
                    "title": title,
                    "original_title": original_title,
                })
        return matches
    except Exception as e:
        print(f"[{now()}] ⚠️  Error fetching events: {e}")
        return None  # None = fetch failed, distinct from [] = no match


def fetch_schedules(event_id: str):
    """Fetch showtimes for a specific event ID. Returns list of show dicts."""
    try:
        params = {"eventID": event_id}
        r = requests.get(FINNKINO_SCHEDULE_URL, params=params, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        shows = []
        for show in root.findall(".//Show"):
            def get(tag):
                el = show.find(tag)
                return el.text if el is not None else ""
            shows.append({
                "theatre": get("Theatre"),
                "start": get("dttmShowStart"),
                "hall": get("TheatreAuditorium"),
                "url": get("ShowURL"),
            })
        return shows
    except Exception as e:
        print(f"[{now()}] ⚠️  Error fetching schedule for event {event_id}: {e}")
        return []


def format_notification(events):
    """Build a nicely formatted Telegram message."""
    lines = ["🎬 <b>The Odyssey tickets are now on Finnkino!</b>\n"]
    for ev in events:
        lines.append(f"🎥 <b>{ev['title']}</b>")
        if ev.get("original_title") and ev["original_title"] != ev["title"]:
            lines.append(f"   ({ev['original_title']})")
        shows = fetch_schedules(ev["id"])
        if shows:
            lines.append(f"\n📅 <b>Showtimes found ({len(shows)} total):</b>")
            # Show first 5 to keep message readable
            for s in shows[:5]:
                dt = s["start"].replace("T", " ") if s["start"] else "?"
                lines.append(f"  • {s['theatre']} — {dt}")
                if s["url"]:
                    lines.append(f"    🎟 <a href=\"{s['url']}\">Buy tickets</a>")
            if len(shows) > 5:
                lines.append(f"  … and {len(shows) - 5} more showings")
        else:
            lines.append("  (No specific showtimes listed yet — check finnkino.fi)")
        lines.append("")
    lines.append("👉 <a href=\"https://www.finnkino.fi\">finnkino.fi</a>")
    return "\n".join(lines)


# ── Main loop ──────────────────────────────────────────────────────────────────

def main():
    print(f"[{now()}] 🚀 Odyssey watcher started. Polling every {POLL_INTERVAL}s.")
    send_telegram(
        "👀 <b>Odyssey watcher is running!</b>\n\n"
        "I'll message you the moment Nolan's <i>The Odyssey</i> tickets appear on Finnkino.\n"
        f"Checking every {POLL_INTERVAL // 60} minutes."
    )

    already_notified_ids = set()

    while True:
        print(f"[{now()}] 🔍 Checking Finnkino for Odyssey...")
        matches = fetch_events()

        if matches is None:
            # Fetch failed — skip this round, don't spam errors
            pass
        elif len(matches) == 0:
            print(f"[{now()}] 😴 Not found yet.")
        else:
            new_matches = [m for m in matches if m["id"] not in already_notified_ids]
            if new_matches:
                print(f"[{now()}] 🎉 Found {len(new_matches)} new Odyssey event(s)! Sending notification.")
                message = format_notification(new_matches)
                send_telegram(message)
                for m in new_matches:
                    already_notified_ids.add(m["id"])
            else:
                print(f"[{now()}] ℹ️  Already notified about all found events.")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
