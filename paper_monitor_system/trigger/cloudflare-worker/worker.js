/**
 * Secure refresh trigger for a static GitHub Pages front end.
 *
 * Required Worker secrets/variables:
 *   GITHUB_PAT       fine-grained PAT with Actions: write on this repository
 *   REFRESH_PASSWORD password typed by the administrator in the browser
 *   GITHUB_OWNER     repository owner
 *   GITHUB_REPO      repository name
 *
 * Optional variables:
 *   GITHUB_REF       default: main
 *   GITHUB_WORKFLOW  default: update-online-papers.yml
 *   ALLOWED_ORIGINS  comma-separated origins, e.g. https://example.github.io
 */

function json(body, status, origin) {
  const headers = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  };
  if (origin) {
    headers["Access-Control-Allow-Origin"] = origin;
    headers["Vary"] = "Origin";
  }
  return new Response(JSON.stringify(body), {status, headers});
}

function allowedOrigin(request, env) {
  const origin = request.headers.get("Origin") || "";
  const allowed = String(env.ALLOWED_ORIGINS || "")
    .split(",")
    .map(x => x.trim())
    .filter(Boolean);
  if (!origin) return "";
  return allowed.includes(origin) ? origin : null;
}

export default {
  async fetch(request, env) {
    const origin = allowedOrigin(request, env);
    if (origin === null) {
      return json({error: "Origin not allowed"}, 403, "");
    }

    const url = new URL(request.url);
    if (request.method === "OPTIONS") {
      const headers = {
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Refresh-Password",
        "Access-Control-Max-Age": "86400",
      };
      if (origin) {
        headers["Access-Control-Allow-Origin"] = origin;
        headers["Vary"] = "Origin";
      }
      return new Response(null, {status: 204, headers});
    }

    if (url.pathname !== "/refresh" || request.method !== "POST") {
      return json({error: "Not found"}, 404, origin || "");
    }

    const supplied = request.headers.get("X-Refresh-Password") || "";
    if (!env.REFRESH_PASSWORD || supplied !== env.REFRESH_PASSWORD) {
      return json({error: "更新密码不正确"}, 401, origin || "");
    }

    const owner = env.GITHUB_OWNER;
    const repo = env.GITHUB_REPO;
    const workflow = env.GITHUB_WORKFLOW || "update-online-papers.yml";
    const ref = env.GITHUB_REF || "main";
    if (!owner || !repo || !env.GITHUB_PAT) {
      return json({error: "Worker 缺少 GitHub 配置"}, 500, origin || "");
    }

    const ghUrl = `https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/actions/workflows/${encodeURIComponent(workflow)}/dispatches`;
    const ghRes = await fetch(ghUrl, {
      method: "POST",
      headers: {
        "Accept": "application/vnd.github+json",
        "Authorization": `Bearer ${env.GITHUB_PAT}`,
        "X-GitHub-Api-Version": "2026-03-10",
        "User-Agent": "online-papers-refresh-worker",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ref}),
    });

    let ghBody = {};
    try { ghBody = await ghRes.json(); } catch (_) { /* no body */ }
    if (!ghRes.ok) {
      return json({
        error: "GitHub workflow 触发失败",
        github_status: ghRes.status,
        github_message: ghBody.message || "",
      }, 502, origin || "");
    }

    return json({
      ok: true,
      message: "更新任务已触发",
      workflow_run_id: ghBody.workflow_run_id || null,
      html_url: ghBody.html_url || null,
    }, 202, origin || "");
  },
};
