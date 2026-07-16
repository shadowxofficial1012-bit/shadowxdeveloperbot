/**
 * OSINT API Relay Worker for Cloudflare Workers
 * Proxies requests to ft-osint-api.duckdns.org and vh-num.vercel.app
 * to bypass Railway's network restrictions.
 *
 * Deploy: paste this code into Cloudflare Workers dashboard
 */

export default {
  async fetch(request, env, ctx) {
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(request.url);

    // Health check
    if (url.pathname === '/health') {
      return new Response(JSON.stringify({ status: 'ok', timestamp: Date.now() }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }

    // Proxy endpoint: GET /proxy?url=<target_url>&<all_other_params_forwarded>
    if (url.pathname === '/proxy') {
      const targetUrl = url.searchParams.get('url');

      if (!targetUrl) {
        return new Response(
          JSON.stringify({ error: 'Missing required param: url' }),
          { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }

      try {
        const target = new URL(targetUrl);

        // Allow both ft-osint-api.duckdns.org and vh-num.vercel.app
        const allowed = target.hostname.includes('ft-osint-api.duckdns.org') ||
                        target.hostname.includes('vh-num.vercel.app');
        if (!allowed) {
          return new Response(
            JSON.stringify({ error: 'Only ft-osint-api.duckdns.org and vh-num.vercel.app are allowed' }),
            { status: 403, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
          );
        }

        // Build proxied URL: forward ALL params except 'url' to the target
        const proxyParams = new URLSearchParams();
        for (const [key, value] of url.searchParams.entries()) {
          if (key !== 'url') {
            proxyParams.set(key, value);
          }
        }
        const queryString = proxyParams.toString();
        const proxyUrl = queryString ? `${targetUrl}?${queryString}` : targetUrl;

        const response = await fetch(proxyUrl, {
          method: 'GET',
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/',
          },
        });

        const body = await response.text();

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

    return new Response(
      JSON.stringify({
        service: 'OSINT API Relay',
        usage: 'GET /proxy?url=<osint_api_url>&<api_params>',
        health: 'GET /health',
        supported: ['ft-osint-api.duckdns.org', 'vh-num.vercel.app'],
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  },
};
