# 🔍 Phone OSINT Bot by @HATHI02

A powerful Telegram bot for Phone Number OSINT (Open Source Intelligence) lookups with a built-in subscription/payment system.

## Features

- 🔍 **Phone Number OSINT Lookup** — Get detailed info (name, address, SIM, IMEI) from any phone number
- 💾 **Data Leak Check** — Check if a number appears in data breaches
- 📡 **SIM & Device Info** — Carrier, state, connection type, IMEI details
- 💳 **UPI Lookup** — Get UPI accounts, bank details, and transaction history linked to a phone number
- 🚗 **Vehicle Lookup** — Get vehicle registration details (owner, insurance, tax) from plate number
- 🎁 **Redeem Codes** — Admin-generated codes for free subscription access
- 📦 **Subscription System** — Unlimited lookups for a fixed duration (Daily/Weekly/Monthly)
- 📸 **Payment Screenshots** — Upload payment proof for admin verification
- 📄 **PDF Reports** — Download styled PDF reports for every lookup
- 🖼 **Image Reports** — Export lookup results as styled PNG images
- 🔁 **Re-export History** — Re-download past reports without using credits
- 👮 **Admin Panel** — Manage users, approve payments, create redeem codes, broadcast messages
- 👥 **User Management** — Ban/unban users, activate plans, check user details
- 📊 **Statistics** — Track total users, lookups, revenue, pending payments
- 🛡 **Rate Limiting** — Prevents API abuse (5 lookups/minute)
- 📢 **Channel Enforcement** — Users must join required channels before using the bot
- 🎨 **Branded UI** — Custom header images, dark hacker-themed PDF reports

## Setup

### 1. Clone & Install

```bash
git clone https://github.com/shadowgamer543254-droid/telegram-osint-bot.git
cd telegram-osint-bot
pip install -r requirements.txt
```

### 2. Configure

Create a `.env` file or set environment variables:

```
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=your_telegram_id_1,your_telegram_id_2
UPI_ID=your_upi_id
UPI_NAME=your_name
OSINT_API_KEY=your_api_key
API_RELAY_URL=https://your-relay.workers.dev/proxy
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
| `/demo` | See a demo phone lookup report |
| `/demo_upi` | See a demo UPI lookup report |
| `/demo_vehicle` | See a demo vehicle lookup report |
| `/upi <number>` | UPI lookup directly |
| `/vehicle <plate>` | Vehicle lookup directly |
| `/approve <tx_id>` | Approve a payment (admin) |
| `/reject <tx_id>` | Reject a payment (admin) |

## Subscription Packages

| Package | Duration | Price |
|---------|----------|-------|
| Daily | 24 hours | ₹10 |
| Weekly | 7 days | ₹100 |
| Monthly | 30 days | ₹200 |

Unlimited lookups while subscription is active.

## Admin Panel

Access via `/admin` command or 🔧 Admin Panel button:
- 👥 View all users with status
- 🔍 Lookup history (all users)
- ✅ Activate subscription plans
- 💳 Add credits manually
- 👤 Check user details
- 🎁 Create redeem codes (single or bulk)
- 📋 View all redeem codes
- 📢 Broadcast messages to all users
- ✅/❌ Approve/reject payment screenshots

## Payment Flow

1. User taps "💰 Buy Plan"
2. Selects a package (Daily/Weekly/Monthly)
3. Scans UPI QR code and pays
4. Uploads payment screenshot
5. Admin receives notification with screenshot
6. Admin approves → subscription activated instantly

## API Endpoints

The bot uses three OSINT APIs:

| Endpoint | Service | Description |
|----------|---------|-------------|
| `ft-osint-api.duckdns.org/api/number` | Phone Lookup | Detailed phone records (name, address, SIM) |
| `ft-osint-api.duckdns.org/api/numleak` | Data Leak | Breach/leak data + calltracer info |
| `ft-osint-api.duckdns.org/api/numtoupi` | UPI Lookup | UPI accounts linked to phone number |
| `vh-num.vercel.app/fetch` | Vehicle Lookup | Vehicle registration details |

**Note:** If Railway blocks direct API access, use the Cloudflare Worker relay (see `relay/README.md`).

## File Structure

```
telegram-osint-bot/
├── main.py              # Bot entry point & message routing
├── config.py            # Configuration (API URLs, keys, packages)
├── database.py          # SQLite database layer
├── api_client.py        # OSINT API integration (all endpoints)
├── handlers.py          # User command handlers (lookup, UPI, vehicle)
├── admin.py             # Admin panel handlers
├── keyboards.py         # Telegram reply & inline keyboards
├── exporter.py          # Styled PNG report generator
├── pdf_exporter.py      # Dark hacker-themed PDF report generator
├── header.py            # Branded header image generator
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker configuration for Railway
├── Procfile             # Railway process file
├── railway.json         # Railway deployment config
├── relay/               # Cloudflare Worker relay (separate deploy)
│   ├── worker.js        # Relay worker code
│   ├── wrangler.example.toml  # Wrangler config template
│   └── README.md        # Relay deployment guide
└── osint_bot.db         # SQLite database (auto-created)
```

## Relay Worker

If Railway blocks direct API access, deploy the Cloudflare Worker relay:

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) → Workers & Pages
2. Create a new Worker → paste `relay/worker.js` code
3. Set `API_RELAY_URL` in Railway environment variables

See `relay/README.md` for detailed instructions.

## Deployment

### Railway (Recommended)

1. Push to GitHub
2. Connect repo to Railway
3. Set environment variables in Railway dashboard
4. Railway auto-deploys using Dockerfile

### Local

```bash
python main.py
```

## License

MIT
