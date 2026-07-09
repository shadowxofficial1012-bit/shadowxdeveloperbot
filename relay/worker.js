/**
 * OSINT API Relay Worker for Cloudflare Workers
 * Proxies requests to ft-osint-api.duckdns.org to bypass Railway's network restrictions.
 *
 * Deploy: npx wrangler deploy
 * Or use Cloudflare dashboard: Workers & Pages > Create > paste this code
 */

export default {
  async fetch(request, env, ctx) {
    // CORS headers for browser-based requests
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(request.url);

    // Health check endpoint
    if (url.pathname === '/health') {
      return new Response(JSON.stringify({ status: 'ok', timestamp: Date.now() }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    // Proxy endpoint: GET /proxy?url=<target_url>&key=<api_key>&num=<number>
    if (url.pathname === '/proxy') {
      const targetUrl = url.searchParams.get('url');
      const key = url.searchParams.get('key');
      const num = url.searchParams.get('num');

      if (!targetUrl || !key || !num) {
        return new Response(
          JSON.stringify({ error: 'Missing required params: url, key, num' }),
          { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }

      try {
        // Validate the target URL is our allowed API
        const target = new URL(targetUrl);
        if (!target.hostname.includes('ft-osint-api.duckdns.org')) {
          return new Response(
            JSON.stringify({ error: 'Only ft-osint-api.duckdns.org is allowed' }),
            { status: 403, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
          );
        }

        // Build the proxied URL
        const proxyUrl = `${targetUrl}?key=${encodeURIComponent(key)}&num=${encodeURIComponent(num)}`;

        // Forward the request with browser-like headers
        const response = await fetch(proxyUrl, {
          method: 'GET',
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/',
          },
        });

        // Read the response body
        const body = await response.text();

        // Return the proxied response with CORS headers
        return new Response(body, {
          status: response.status,
          headers: {
            ...corsHeaders,
            'Content-Type': 'application/json',
          },
        });
      } catch (err) {
        return new Response(
          JSON.stringify({ error: `Relay error: ${err.message}` }),
          { status: 502, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }
    }

    // Default: show usage info
    return new Response(
      JSON.stringify({
        service: 'OSINT API Relay',
        usage: 'GET /proxy?url=<osint_api_url>&key=<api_key>&num=<phone_number>',
        health: 'GET /health',
        example: '/proxy?url=https://ft-osint-api.duckdns.org/api/number&key=lesbian-hathi&num=9876543210',
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  },
};
