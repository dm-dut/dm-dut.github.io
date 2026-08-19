/*
 * Public browser configuration.
 *
 * refreshEndpoint is NOT a secret. It points to the small server-side trigger
 * (for example the Cloudflare Worker included in trigger/cloudflare-worker/).
 * Never put a GitHub PAT, publisher API key, or refresh password in this file.
 */
window.PAPER_TRACKER_CONFIG = {
  refreshEndpoint: "", // e.g. "https://paper-refresh.example.workers.dev/refresh"
  refreshPollIntervalMs: 5000,
  refreshTimeoutMs: 10 * 60 * 1000,
};
