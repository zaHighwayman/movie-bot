# 🎬 Odyssey Ticket Watcher

Monitors Finnkino 24/7 and sends you a Telegram message the moment Nolan's *The Odyssey* tickets go on sale.

---

## Setup — takes about 10 minutes

### Step 1 — Create a Telegram bot

1. Open Telegram and search for **@BotFather**
2. Send it `/newbot`
3. Follow the prompts — pick any name and username
4. BotFather gives you a token that looks like: `7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
5. **Copy this token** — you'll need it in Step 3

### Step 2 — Get your Chat ID

1. Search Telegram for **@userinfobot**
2. Start it (`/start`)
3. It replies with your user ID, e.g. `Id: 123456789`
4. **Copy that number** — it's your Chat ID

### Step 3 — Deploy on Railway (free)

1. Go to **[railway.app](https://railway.app)** and sign up (GitHub login is easiest)
2. Click **New Project → Deploy from GitHub repo**
3. Push this folder to a GitHub repo first (or use Railway's CLI — see below)
4. Once the repo is connected, go to your service → **Variables** tab
5. Add these two environment variables:

| Variable | Value |
|---|---|
| `TELEGRAM_TOKEN` | the token from Step 1 |
| `TELEGRAM_CHAT_ID` | your ID from Step 2 |

6. Railway will automatically deploy and start the watcher
7. You'll get a Telegram message confirming it's running ✅

#### Optional: change polling interval
Add a third variable if you want:

| Variable | Value |
|---|---|
| `POLL_INTERVAL_SECONDS` | `300` (5 min) or `600` (10 min, default) |

---

### Alternative: push via Railway CLI

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

Then set variables:
```bash
railway variables set TELEGRAM_TOKEN=your_token_here
railway variables set TELEGRAM_CHAT_ID=your_chat_id_here
```

---

## How it works

- Every 10 minutes, it hits `https://www.finnkino.fi/xml/Events/` and scans for any movie with "odyssey" in the title
- When found, it fetches showtimes from `https://www.finnkino.fi/xml/Schedule/` and sends you a Telegram message with times + direct ticket links
- It won't spam you — each event is only notified once
- If it crashes, Railway restarts it automatically

---

## Files

```
watcher.py        — the main script
requirements.txt  — just "requests"
Procfile          — tells Railway to run watcher.py
railway.toml      — Railway config (auto-restart on failure)
```
