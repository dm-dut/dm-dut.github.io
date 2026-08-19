/*
 * Public browser configuration. Do NOT put any API key, GitHub token, or
 * refresh password in this file.
 */
window.PAPER_TRACKER_CONFIG = {
  // Optional secure one-click trigger (Cloudflare Worker code is included in
  // paper_monitor_system/trigger/cloudflare-worker/). Leave blank until deployed.
  refreshEndpoint: "",

  // Safe fallback when refreshEndpoint is blank. Clicking “立即更新” opens the
  // repository's Actions workflow instead of showing a configuration error.
  actionsUrl: "https://github.com/dm-dut/dm-dut.github.io/actions/workflows/update-paper-monitor.yml",

  refreshPollIntervalMs: 5000,
  refreshTimeoutMs: 10 * 60 * 1000,
};
