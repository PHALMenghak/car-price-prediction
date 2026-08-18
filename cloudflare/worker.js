/**
 * cloudflare/worker.js
 * Khmer24 API Relay Worker
 *
 * Deployed on Cloudflare Workers (free tier: 100,000 req/day).
 * Acts as a trusted bridge between GitHub Actions (blocked Azure IP)
 * and the Khmer24 API (protected by Cloudflare Bot Management).
 *
 * Security:
 *   - All requests must include the header: X-Relay-Key: <your-secret>
 *   - Only Khmer24 API domains are allowed as targets (allowlist)
 *
 * Deploy:
 *   1. Go to dash.cloudflare.com > Workers & Pages > Create Worker
 *   2. Paste this entire file > Deploy
 *   3. Note your Worker URL: https://khmer24-relay.<yourname>.workers.dev
 *   4. In Worker Settings > Variables > add RELAY_KEY = <your-secret>
 */

// Allowed target domains (security allowlist)
const ALLOWED_HOSTS = [
  "api-posts.khmer24.com",
  "api.khmer24.com",
];

// Main request handler
export default {
  async fetch(request, env) {
    // Step 1: Only allow GET requests
    if (request.method !== "GET") {
      return jsonResponse({ error: "Method not allowed" }, 405);
    }

    // Step 2: Validate the relay secret key
    const relayKey = request.headers.get("X-Relay-Key");
    const expectedKey = env.RELAY_KEY;

    if (!expectedKey) {
      return jsonResponse({ error: "Worker misconfigured: RELAY_KEY not set" }, 500);
    }
    if (!relayKey || relayKey !== expectedKey) {
      return jsonResponse({ error: "Unauthorized: invalid X-Relay-Key" }, 401);
    }

    // Step 3: Parse and validate the target URL
    // The caller sends the full Khmer24 URL as a ?target= query param
    // e.g. ?target=https://api-posts.khmer24.com/feed&category=cars-for-sale&limit=30
    const url = new URL(request.url);
    const targetParam = url.searchParams.get("target");

    if (!targetParam) {
      return jsonResponse({ error: "Missing required query param: target" }, 400);
    }

    let targetUrl;
    try {
      targetUrl = new URL(targetParam);
    } catch (e) {
      return jsonResponse({ error: "Invalid target URL" }, 400);
    }

    // Security: only allow requests to whitelisted Khmer24 domains
    if (!ALLOWED_HOSTS.includes(targetUrl.hostname)) {
      return jsonResponse(
        { error: `Target host not allowed: ${targetUrl.hostname}` },
        403
      );
    }

    // Step 4: Forward remaining query params to the target URL
    // e.g. category=cars-for-sale&offset=0&limit=30&lang=en&sort=recent&fields=all
    url.searchParams.forEach((value, key) => {
      if (key !== "target") {
        targetUrl.searchParams.set(key, value);
      }
    });

    // Step 5: Call the real Khmer24 API from inside Cloudflare's network
    let khmerResponse;
    try {
      khmerResponse = await fetch(targetUrl.toString(), {
        method: "GET",
        headers: {
          "Accept":          "application/json, text/plain, */*",
          "Accept-Language": "en-US,en;q=0.9,km;q=0.8",
          "Origin":          "https://www.khmer24.com",
          "Referer":         "https://www.khmer24.com/",
          "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
          "display-type":    "desktop",
          "Sec-Fetch-Dest":  "empty",
          "Sec-Fetch-Mode":  "cors",
          "Sec-Fetch-Site":  "same-site",
        },
      });
    } catch (err) {
      return jsonResponse({ error: `Failed to reach Khmer24: ${err.message}` }, 502);
    }

    // Step 6: Return Khmer24's response back to the caller
    const body = await khmerResponse.text();
    return new Response(body, {
      status: khmerResponse.status,
      headers: {
        "Content-Type":                "application/json; charset=utf-8",
        "Access-Control-Allow-Origin": "*",
        "X-Relay-Status":              String(khmerResponse.status),
      },
    });
  },
};

// Helper
function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
