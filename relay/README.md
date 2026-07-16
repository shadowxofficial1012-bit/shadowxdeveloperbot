# OSINT API Relay - Cloudflare Worker

Bypasses Railway's network restrictions by proxying requests to `ft-osint-api.duckdns.org` and `vh-num.vercel.app` through Cloudflare's edge network.

## Supported APIs

| Domain | API |
|--------|-----|
| `ft-osint-api.duckdns.org` | Phone lookup, UPI lookup, Data leak |
| `vh-num.vercel.app` | Vehicle registration lookup |

## Quick Deploy (Cloudflare Dashboard)

1. Go to https://dash.cloudflare.com → **Workers & Pages**
2. Click **Create** → **Create Worker**
3. Name it `telegram-osint-bot`
4. Click **Deploy**, then **Edit code**
5. Delete the default code, paste the contents of `worker.js`
6. Click **Deploy**
7. Your relay URL will be: `https://telegram-osint-bot.<your-subdomain>.workers.dev`

**Important:** The worker name must match the URL in `config.py` (`API_RELAY_URL`).

## Test Your Relay

After deployment, test it:

```bash
# Health check
curl "https://telegram-osint-bot.YOUR_SUBDOMAIN.workers.dev/health"

# Phone lookup
curl "https://telegram-osint-bot.YOUR_SUBDOMAIN.workers.dev/proxy?url=https://ft-osint-api.duckdns.org/api/number&key=YOUR_API_KEY&num=9876543210"

# Vehicle lookup
curl "https://telegram-osint-bot.YOUR_SUBDOMAIN.workers.dev/proxy?url=https://vh-num.vercel.app/fetch&vehicle=MH12AB1234"
```

## Configure Your Bot

Set the `API_RELAY_URL` environment variable in Railway:

```
API_RELAY_URL=https://telegram-osint-bot.YOUR_SUBDOMAIN.workers.dev/proxy
```

In Railway dashboard:
1. Go to your service → **Variables**
2. Add: `API_RELAY_URL` = `https://telegram-osint-bot.YOUR_SUBDOMAIN.workers.dev/proxy`
3. Redeploy

**Note:** If your APIs work directly (no Railway blocking), you can leave `API_RELAY_URL` empty.

## How It Works

```
Railway Bot → Cloudflare Worker → ft-osint-api.duckdns.org
                                  vh-num.vercel.app
                                    ↑
                              (Cloudflare has no
                               network restrictions)
```

## Deployment Notes

- **Do NOT deploy this via Railway** — it's a separate Cloudflare Worker
- The `wrangler.example.toml` file is a template; copy it to `wrangler.toml` if using CLI deploy
- Railway auto-detects `wrangler.toml` and may try to deploy it, breaking your bot build
