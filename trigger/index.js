// Cloudflare side of OnePieceSnapshot.
// - cron: presses "run" on the GitHub workflow (GitHub's own schedule never fired, 11/10).
// - fetch: tiny private door to the R2 bucket for the workflow (X-Key = UPLOAD_KEY).
//     GET /get?key=...   PUT /put?key=...   GET /list?prefix=...
export default {
  async scheduled(_event, env) {
    const r = await fetch(
      "https://api.github.com/repos/miniworld7373-ship-it/OnePieceSnapshot/actions/workflows/snapshot.yml/dispatches",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GH_TOKEN}`,
          Accept: "application/vnd.github+json",
          "User-Agent": "onepiece-snapshot-trigger",
        },
        body: JSON.stringify({ ref: "main" }),
      },
    );
    if (r.status !== 204) throw new Error(`GitHub dispatch ${r.status}: ${await r.text()}`);
  },

  async fetch(request, env) {
    if (!env.UPLOAD_KEY || request.headers.get("X-Key") !== env.UPLOAD_KEY) return new Response("no", { status: 403 });
    const url = new URL(request.url);
    const key = url.searchParams.get("key");
    if (url.pathname === "/get" && key) {
      const obj = await env.BUCKET.get(key);
      return obj ? new Response(obj.body) : new Response("missing", { status: 404 });
    }
    if (url.pathname === "/put" && key && request.method === "PUT") {
      await env.BUCKET.put(key, request.body);
      return new Response("ok");
    }
    if (url.pathname === "/list") {
      const out = [];
      let cursor;
      do {
        const page = await env.BUCKET.list({ prefix: url.searchParams.get("prefix") || "", cursor });
        out.push(...page.objects.map((o) => `${o.key}\t${o.size}`));
        cursor = page.truncated ? page.cursor : undefined;
      } while (cursor);
      return new Response(out.join("\n"));
    }
    return new Response("?", { status: 400 });
  },
};
