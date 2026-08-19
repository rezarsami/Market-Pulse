// Backend base URL. In dev, Vite proxies /api -> localhost:8000 (see
// vite.config.js). In production, set VITE_API_BASE_URL to the deployed
// backend's origin (e.g. https://market-pulse-api.onrender.com) at build
// time, or leave unset to use same-origin /api if the backend is served
// behind the same reverse proxy as the frontend.
const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

// A per-tab session id, kept in memory only (never localStorage), sent as
// a header so the backend's rate limiter can bucket by session rather
// than just raw IP.
const SESSION_ID = crypto.randomUUID();

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Session-Id": SESSION_ID,
      ...(options.headers || {}),
    },
  });

  if (!res.ok) {
    let detail;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      detail = res.statusText;
    }
    const err = new Error(
      typeof detail === "object" ? detail.error || JSON.stringify(detail) : detail
    );
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return res.json();
}

export function analyzeTicker({ ticker, question, strategyOverride }) {
  return request("/analyze", {
    method: "POST",
    body: JSON.stringify({
      ticker,
      question: question || undefined,
      strategy_override: strategyOverride || undefined,
    }),
  });
}

export function fetchPriceHistory({ ticker, period }) {
  const params = new URLSearchParams({ ticker, period });
  return request(`/price-history?${params.toString()}`);
}

export function fetchStats({ ticker }) {
  const params = new URLSearchParams({ ticker });
  return request(`/stats?${params.toString()}`);
}

export function fetchAnalytics({ ticker, period }) {
  const params = new URLSearchParams({ ticker, period: period || "1Y" });
  return request(`/analytics?${params.toString()}`);
}

export function fetchHealth() {
  return request("/health");
}
