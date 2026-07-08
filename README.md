# \U0001f50d OSINT Instagram Bot

A powerful Telegram bot for Instagram OSINT (Open Source Intelligence) lookups with a built-in credit/payment system.

## Features

- \U0001f50d **Instagram OSINT Lookup** — Get detailed info from any public Instagram username
- \U0001f4b0 **Credit System** — Pay-per-lookup with UPI payment support
- \U0001f4f7 **Payment Screenshots** — Upload payment proof for admin verification
- \U0001f3f7\ufe0f **Admin Panel** — Manage users, approve payments, view stats
- \U0001f465 **User Management** — Ban/unban users, add credits manually
- \U0001f4ca **Statistics** — Track total users, lookups, revenue
- \U0001f4dd **Beautiful Formatting** — Rich HTML-formatted responses with profile pictures

## Setup

### 1. Clone & Install

```bash
pip install -r requirements.txt
```

### 2. Configure

Copy `.env.example` to `.env` and fill in your details:

```bash
cp .env.example .env
```

Edit `.env`:
```
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=your_telegram_id
UPI_ID=your_upi_id
UPI_NAME=your_name
```

### 3. Run

```bash
python main.py
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot & show main menu |
| `/help` | Show usage instructions |
| `/admin` | Access admin panel (admin only) |

## Credit Packages

| Package | Credits | Price |
|---------|---------|-------|
| Starter | 10 | \u20b949 |
| Pro | 50 | \u20b9199 |
| Unlimited | 9999 | \u20b9499 |

New users get **3 FREE credits** to start.

## Admin Panel

Access via `/admin` command. Features:
- View bot statistics
- Approve/reject pending payments
- Add credits to users manually
- Ban/unban users
- Look up user details

## Payment Flow

1. User taps "Buy Credits"
2. Selects a package
3. Sends UPI payment
4. Uploads payment screenshot
5. Admin reviews & approves
6. Credits added automatically

## File Structure

```
osint-bot/
\u251c\u2500\u2500 main.py           # Bot entry point
\u251c\u2500\u2500 config.py          # Configuration
\u251c\u2500\u2500 database.py        # SQLite database layer
\u251c\u2500\u2500 api_client.py      # OSINT API integration
\u251c\u2500\u2500 handlers.py        # User command handlers
\u251c\u2500\u2500 admin.py           # Admin panel handlers
\u251c\u2500\u2500 keyboards.py       # Telegram keyboards
\u251c\u2500\u2500 requirements.txt   # Python dependencies
\u251c\u2500\u2500 .env.example       # Environment template
\u251c\u2500\u2500 .env               # Your config (git ignored)
\u2514\u2500\u2500 osint_bot.db       # SQLite database (auto-created)
```

## API

This bot uses the [ft-osint-api](https://ft-osint-api.duckdns.org) for Instagram data retrieval.
