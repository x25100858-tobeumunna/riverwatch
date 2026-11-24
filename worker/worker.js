/**
 * River Watch - Cloudflare Worker (server-side home for the AI key).
 *
 * The page sends the prepared prompt here; this Worker adds the Groq key and
 * forwards it to Groq. The key lives ONLY in Cloudflare as an encrypted secret
 * named GROQ_API_KEY (Workers > riverwatch > Settings > Variables and Secrets).
 * It is never in this file, the repository or the web page.
 *
 * Guard rails (so a copied Worker URL cannot run up cost or be used as a
 * general free AI endpoint):
 *  - only the River Watch page's origins may call it (CORS + Origin check)
 *  - model fixed to openai/gpt-oss-120b, answer capped at 900 tokens
 *  - prompt size capped (~6,000 tokens), POST /chat only
 *  - the key is on Groq's Free plan (no card): a leak costs nothing, the
 *    worst case is the free daily token limit being used up
 */
const ALLOWED_ORIGINS = [
  "https://x25100858-tobeumunna.github.io",
  "http://localhost:8765",
  "http://127.0.0.1:8765",
];
const MODEL = "openai/gpt-oss-120b";
const MAX_PROMPT_CHARS = 24000;
const MAX_ANSWER_TOKENS = 900;

function cors(origin) {
  return {
    "Access-Control-Allow-Origin": ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0],
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Expose-Headers": "retry-after",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
}
const json = (obj, status, origin, extra = {}) =>
  new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json", ...cors(origin), ...extra } });

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";
    const url = new URL(request.url);

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(origin) });
    if (request.method === "GET" && url.pathname === "/") return json({ ok: true, service: "River Watch AI relay", model: MODEL, key_configured: !!env.GROQ_API_KEY }, 200, origin);
    if (!ALLOWED_ORIGINS.includes(origin)) return json({ error: { message: "Origin not allowed" } }, 403, origin);
    if (request.method !== "POST" || url.pathname !== "/chat") return json({ error: { message: "Use POST /chat" } }, 404, origin);
    if (!env.GROQ_API_KEY) return json({ error: { message: "Server key not configured (GROQ_API_KEY secret missing)" } }, 500, origin);

    let body;
    try { body = await request.json(); } catch { return json({ error: { message: "Invalid JSON" } }, 400, origin); }
    const messages = Array.isArray(body.messages) ? body.messages : null;
    if (!messages || !messages.length || messages.length > 8 ||
        !messages.every(m => ["system", "user", "assistant"].includes(m.role) && typeof m.content === "string"))
      return json({ error: { message: "messages must be 1-8 {role, content} items" } }, 400, origin);
    const size = messages.reduce((a, m) => a + m.content.length, 0);
    if (size > MAX_PROMPT_CHARS) return json({ error: { message: `Prompt too large (${size} chars)` } }, 413, origin);

    const upstream = await fetch("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${env.GROQ_API_KEY}` },
      body: JSON.stringify({ model: MODEL, messages, max_completion_tokens: MAX_ANSWER_TOKENS, reasoning_effort: "low" }),
    });
    const data = await upstream.json().catch(() => ({ error: { message: "Bad response from Groq" } }));
    const extra = upstream.headers.get("retry-after") ? { "retry-after": upstream.headers.get("retry-after") } : {};
    // pass back only what the page needs (never any header or detail that could reveal the key)
    const out = upstream.ok
      ? { model: data.model, choices: [{ message: { content: data.choices?.[0]?.message?.content || "" } }], usage: data.usage }
      : { error: { message: data.error?.message || `Groq error ${upstream.status}` } };
    return json(out, upstream.status, origin, extra);
  },
};
