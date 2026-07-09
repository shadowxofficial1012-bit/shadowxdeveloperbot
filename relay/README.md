# OSINT API Relay - Cloudflare Worker

Bypasses Railway's network restrictions by proxying requests to `ft-osint-api.duckdns.org` through Cloudflare's edge network.

## Quick Deploy (3 methods)

### Method 1: Cloudflare Dashboard (Easiest - No CLI needed)

1. Go to https://dash.cloudflare.com → **Workers & Pages**
2. Click **Create** → **Create Worker**
3. Name it `osint-api-relay`
4. Click **Deploy**, then **Edit code**
5. Delete the default code, paste the contents of `worker.js`
6. Click **Deploy**
7. Your relay URL will be: `https://osint-api-relay.<your-subdomain>.workers.dev`

### Method 2: Wrangler CLI

```bash
cd relay/
npm install -g wrangler
wrangler login
wrangler deploy
```

### Method 3: Via npm scripts

```bash
cd relay/
npm init -y
npm install -g wrangler
wrangler login
wrangler deploy
```

## Test Your Relay

After deployment, test it:

```bash
# Replace with your actual worker URL
curl "https://osint-api-relay.YOUR_SUBDOMAIN.workers.dev/proxy?url=https://ft-osint-api.duckdns.org/api/number&key=lesbian-hathi&num=9876543210"
```

You should get a JSON response with phone number data.

## Configure Your Bot

Set the `API_RELAY_URL` environment variable in Railway:

```
API_RELAY_URL=https://osint-api-relay.YOUR_SUBDOMAIN.workers.dev/proxy
```

In Railway dashboard:
1. Go to your service → **Variables**
2. Add: `API_RELAY_URL` = `https://osint-api-relay.YOUR_SUBDOMAIN.workers.dev/proxy`
3. Redeploy

## How It Works

```
Railway Bot → Cloudflare Worker → ft-osint-api.duckdns.org
                                    ↑
                              (Cloudflare has no
                               network restrictions)
```

Cloudflare Workers run on Cloudflare's edge network, which doesn't have the same IP blocks as Railway. The worker simply forwards your API requests and returns the response.
