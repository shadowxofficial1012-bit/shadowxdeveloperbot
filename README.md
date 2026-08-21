# HathixShadow OSINT Bot

A multi-service Telegram OSINT bot by Utkarsh with QR-based payments, 7 API lookup services, and dark-themed PDF reports.

## Features

- **7 OSINT Services** — IP, Phone, Name, Vehicle, M-Parivahan, HotX, Aadhaar Family
- **QR Payment System** — Auto-generated QR codes with exact amount, single-use tokens
- **PDF Reports** — Dark hacker-themed PDF download for every lookup
- **Subscription System** — Unlimited lookups for Daily/Weekly/Monthly plans
- **Admin Panel** — Manage users, approve payments, create redeem codes, broadcast
- **Channel Enforcement** — Users must join required channels before use
- **Rate Limiting** — 5 lookups/minute per user
- **Redeem Codes** — Admin-generated codes for free access

## Services

| Service | Input | Description |
|---------|-------|-------------|
| IP Lookup | IP address | ISP, location, timezone, coordinates |
| Num Info | 10-digit phone | Telecom, carrier, location |
| Name Info | Full name | Identity details |
| Vehicle Lookup | Plate number | Full vehicle registration info |
| M-Parivahan | Plate number | Government vehicle database |
| HotX Lookup | 10-digit phone | Deep phone intelligence |
| Aadhaar Family | 12-digit Aadhaar | Family member trace |

## Setup

### 1. Clone & Install

```bash
git clone https://github.com/shadowxofficial1012-bit/shadowxdeveloperbot.git
cd shadowxdeveloperbot
pip install -r requirements.txt
```

### 2. Configure

Create a `.env` file:

```
BOT_TOKEN=your_bot_token
ADMIN_IDS=7392346621,8722759285
UPI_ID=your_upi_id@paytm
UPI_NAME=Your Name
API_RELAY_URL=https://your-relay.workers.dev/proxy
```

### 3. Run

```bash
python main.py
```

## Subscription Packages

| Package | Duration | Price |
|---------|----------|-------|
| 1 Day Pack | 24 hours | ₹20 |
| 1 Week Pack | 168 hours | ₹200 |
| 1 Month Pack | 720 hours | ₹400 |

## Payment Flow

1. User taps "Buy Plan"
2. Selects a package
3. Bot generates a **QR code with exact UPI amount** and unique single-use token
4. User scans QR and pays the exact amount
5. User sends payment screenshot
6. QR token is marked as used (single-use enforcement)
7. Admin receives screenshot notification with approve/reject buttons
8. Admin approves → subscription activated instantly

## Admin Panel

Access via `/admin` command or the Admin Panel button:

| Action | Description |
|--------|-------------|
| Total Users | View all users with status |
| Lookup History | All recent lookups across users |
| Activate Plan | Manually add subscription hours |
| Add Credits | Add credits to a user |
| Check User | View detailed user info |
| Create Code | Generate single or bulk redeem codes |
| View All Codes | List all redeem codes |
| Broadcast | Send message to all users |
| API Health | Check all API endpoint status |

## API Endpoints

| Endpoint | Service |
|----------|---------|
| `ip-info-api.hcjffjggjf.workers.dev` | IP Info |
| `full-vehicle-info.vercel.app` | Vehicle Full |
| `m-parivahan-api.onrender.com` | M-Parivahan |
| `name-info-2.vercel.app` | Name Info |
| `hot-x-api.razaisback509.workers.dev` | HotX |
| `aadhaar-family-xyz.rasiksarkarrasiksarkar.workers.dev` | Aadhaar Family |
| `numinfo-1m.hcjffjggjf.workers.dev` | Num Info |

## File Structure

```
shadowxdeveloperbot/
├── main.py              # Bot entry point & message routing
├── config.py            # Configuration (API URLs, packages, branding)
├── database.py          # SQLite database (users, transactions, QR codes)
├── api_client.py        # 7 OSINT API integrations
├── handlers.py          # All user handlers (lookups, payments, callbacks)
├── admin.py             # Admin panel handlers
├── keyboards.py         # Reply & inline keyboards
├── qr_payment.py        # QR code generator with exact UPI amount
├── pdf_exporter.py      # Dark-themed PDF report generator
├── header.py            # Branded header image generator
├── user_data_store.py   # JSON user data store (backup)
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker configuration
├── Procfile             # Process file
├── railway.json         # Railway deployment config
└── osint_bot.db         # SQLite database (auto-created)
```

## Deployment

### Railway

1. Push to GitHub
2. Connect repo to Railway
3. Set environment variables
4. Auto-deploys via Dockerfile

### Local

```bash
python main.py
```

## License

MIT
