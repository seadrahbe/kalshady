// API client for the ShadyPredict backend.
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8010";

let token = localStorage.getItem("sp_token") || null;
export const getToken = () => token;
export function setToken(t) {
  token = t;
  if (t) localStorage.setItem("sp_token", t);
  else localStorage.removeItem("sp_token");
}

let adminKey = localStorage.getItem("sp_admin_key") || "";
export const getAdminKey = () => adminKey;
export function setAdminKey(k) {
  adminKey = k || "";
  if (k) localStorage.setItem("sp_admin_key", k);
  else localStorage.removeItem("sp_admin_key");
}

async function req(path, { method = "GET", body, auth = true, adminAuth = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && token) headers["Authorization"] = `Bearer ${token}`;
  if (adminAuth) headers["X-Admin-Key"] = adminKey;
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail;
    try { detail = (await res.json()).detail; } catch { detail = res.statusText; }
    const err = new Error(typeof detail === "string" ? detail : `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  if (res.status === 204) return null;
  return (res.headers.get("content-type") || "").includes("application/json") ? res.json() : res.text();
}

const uuid = () =>
  (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`);

export const api = {
  login: (pan, otp) => req("/api/auth/login", { method: "POST", auth: false, body: { pan, otp } }),
  me: () => req("/api/auth/me"),
  wallet: () => req("/api/wallet"),
  deposit: (amount_cents) =>
    req("/api/wallet/deposit", { method: "POST", body: { amount_cents, idempotency_key: uuid() } }),
  markets: () => req("/api/markets"),
  market: (id) => req(`/api/markets/${id}`),
  bet: (id, outcome_id, stake_cents) =>
    req(`/api/markets/${id}/bet`, { method: "POST", body: { outcome_id, stake_cents, idempotency_key: uuid() } }),
  portfolio: () => req("/api/portfolio"),
};

export const admin = {
  check: () => req("/api/admin/check", { adminAuth: true }),
  createMarket: (title, outcomes, outcome_prices) =>
    req("/api/admin/markets", { method: "POST", adminAuth: true, body: { title, outcomes, outcome_prices } }),
  setOdds: (id, prices) =>
    req(`/api/admin/markets/${id}/odds`, { method: "POST", adminAuth: true, body: { prices } }),
  resolve: (id, winning_outcome_id) =>
    req(`/api/admin/markets/${id}/resolve`, { method: "POST", adminAuth: true, body: { winning_outcome_id } }),
  voidMarket: (id) =>
    req(`/api/admin/markets/${id}/void`, { method: "POST", adminAuth: true }),
  closeMarket: (id) =>
    req(`/api/admin/markets/${id}/close`, { method: "POST", adminAuth: true }),
  cashout: (otp) =>
    req("/api/admin/cashout", { method: "POST", adminAuth: true, body: { otp } }),
};
