# 🔍 Phone Number OSINT Bot

A powerful Telegram bot for Phone Number OSINT (Open Source Intelligence) lookups with a built-in credit/payment system.

## Features

- 🔍 **Phone Number OSINT Lookup** — Get detailed info from any phone number
- 💾 **Data Leak Check** — Check if a number appears in data breaches
- 📡 **SIM & Device Info** — Carrier, state, connection type details
- 💳 **Credit System** — Pay-per-lookup with UPI payment support
- 📸 **Payment Screenshots** — Upload payment proof for admin verification
- 👮 **Admin Panel** — Manage users, approve payments, view stats
- 👥 **User Management** — Ban/unban users, add credits manually
- 📊 **Statistics** — Track total users, lookups, revenue
- 📝 **Beautiful Formatting** — Rich HTML-formatted responses with styled reports

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
OSINT_API_KEY=your_api_key
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
| Starter | 10 | ₹49 |
| Pro | 50 | ₹199 |
| Unlimited | 9999 | ₹499 |

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

## API Endpoints

The bot uses two OSINT APIs:

| Endpoint | Description |
|----------|-------------|
| `/api/number` | Phone number lookup with records |
| `/api/numleak` | Data leak information |

## File Structure

```
osint-bot/
├── main.py           # Bot entry point
├── config.py         # Configuration
├── database.py       # SQLite database layer
├── api_client.py     # OSINT API integration
├── handlers.py       # User command handlers
├── admin.py          # Admin panel handlers
├── keyboards.py      # Telegram keyboards
├── exporter.py       # Report image generator
├── header.py         # Branded header image
├── requirements.txt  # Python dependencies
├── .env.example      # Environment template
├── .env              # Your config (git ignored)
└── osint_bot.db      # SQLite database (auto-created)
```

## API

This bot uses the [ft-osint-api](https://ft-osint-api.duckdns.org) for phone number data retrieval.

## License

MIT
