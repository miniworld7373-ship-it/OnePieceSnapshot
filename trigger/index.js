// Cron trigger: GitHub's own schedule never fired on this repo (11/10), so Cloudflare presses "run".
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
};
