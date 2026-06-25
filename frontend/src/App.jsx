import './App.css';
import MarketsPage from './views/pages/Market.jsx';
import AdminPage from './views/pages/Admin.jsx';
import Toast from './views/components/Toast.jsx';
import { api, setToken, getToken } from './api.js';

import { useState, useEffect, useCallback } from "react";

/* ─── PALETTE (Kalshi-faithful) ─── */
export const C = {
  bgPage: "#0f1117", bgSidebar: "#13151c", bgCard: "#1a1d27", bgCardHover: "#1f2235",
  bgInput: "#1a1d27", border: "#2a2d3e", borderLight: "#33374f",
  textPrimary: "#e8eaf0", textSecondary: "#8b90a8", textMuted: "#5a5f7a",
  green: "#00c076", greenDim: "rgba(0,192,118,0.12)", greenBorder: "rgba(0,192,118,0.3)",
  red: "#f03d3d", redDim: "rgba(240,61,61,0.12)", redBorder: "rgba(240,61,61,0.3)",
  accent: "#5b6af0", accentDim: "rgba(91,106,240,0.15)", yellow: "#f5c842", purple: "#9b72f5",
};

export const CATEGORIES = [
  { id: "all", label: "All markets", icon: "▦" },
  { id: "toorcamp", label: "ToorCamp", icon: "👾" },
];

export const SORT_OPTS = [
  { val: "volume", label: "Most volume" },
  { val: "newest", label: "Newest" },
  { val: "certain", label: "Most certain" },
];

const inputStyle = {
  background: C.bgInput, border: `1px solid ${C.border}`, color: C.textPrimary,
  borderRadius: 8, padding: "10px 12px", fontSize: 14, outline: "none", width: "100%",
};
const btnPrimary = {
  background: C.accent, color: "#fff", border: "none", borderRadius: 8,
  padding: "10px 16px", fontSize: 14, fontWeight: 700, cursor: "pointer", width: "100%",
};

/* ─── LOGIN ─── */
function Login({ onAuthed }) {
  const [pan, setPan] = useState("");
  const [otp, setOtp] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const res = await api.login(pan.replace(/\s/g, ""), otp.trim());
      setToken(res.session_token);
      onAuthed(res);
    } catch (e2) {
      setErr(e2.message || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: C.bgPage, display: "flex", alignItems: "center",
      justifyContent: "center", fontFamily: "system-ui,-apple-system,sans-serif", color: C.textPrimary }}>
      <form onSubmit={submit} style={{ width: 340, background: C.bgCard, border: `1px solid ${C.border}`,
        borderRadius: 14, padding: 28, display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
          <div style={{ width: 30, height: 30, borderRadius: 8, background: C.accent, display: "flex",
            alignItems: "center", justifyContent: "center", fontSize: 16 }}>🎰</div>
          <span style={{ fontWeight: 800, fontSize: 18 }}>Kal<span style={{ color: C.accent }}>shady</span></span>
        </div>
        <p style={{ margin: 0, fontSize: 12, color: C.textMuted }}>Sign in with your ShadyBucks card.</p>
        <input style={inputStyle} placeholder="Card number" value={pan} onChange={e => setPan(e.target.value)} />
        <input style={inputStyle} placeholder="One-time code (OTP)" value={otp} onChange={e => setOtp(e.target.value)} />
        {err && <p style={{ margin: 0, color: C.red, fontSize: 12 }}>{err}</p>}
        <button style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }} disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

/* ─── DEPOSIT MODAL ─── */
function DepositModal({ onClose, onDone, showToast }) {
  const [amount, setAmount] = useState("50");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    const cents = Math.round(parseFloat(amount) * 100);
    if (!cents || cents <= 0) return;
    setBusy(true);
    try {
      const res = await api.deposit(cents);
      showToast(`✅ Deposited ${amount} SB`);
      onDone(res.wallet);
      onClose();
    } catch (e2) {
      showToast(`❌ ${e2.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 500,
      display: "flex", alignItems: "center", justifyContent: "center" }}>
      <form onClick={e => e.stopPropagation()} onSubmit={submit}
        style={{ width: 320, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14,
          padding: 24, display: "flex", flexDirection: "column", gap: 14 }}>
        <p style={{ margin: 0, fontWeight: 700, fontSize: 15 }}>Add ShadyBucks</p>
        <p style={{ margin: 0, fontSize: 12, color: C.textMuted }}>
          Moves bucks from your bank account into your wallet. No OTP needed.
        </p>
        <input style={inputStyle} type="number" min="1" step="1" value={amount}
          onChange={e => setAmount(e.target.value)} placeholder="Amount (SB)" />
        <button style={{ ...btnPrimary, opacity: busy ? 0.6 : 1 }} disabled={busy}>
          {busy ? "Depositing…" : "Deposit"}
        </button>
        <button type="button" onClick={onClose} style={{ background: "none", border: "none",
          color: C.textMuted, fontSize: 12, cursor: "pointer" }}>Cancel</button>
      </form>
    </div>
  );
}

/* ─── ROOT APP ─── */
export default function App() {
  const [authed, setAuthed] = useState(false);
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState(null);
  const [wallet, setWallet] = useState({ balance_cents: 0, balance_display: "0.00" });
  const [toast, setToast] = useState(null);
  const [showDeposit, setShowDeposit] = useState(false);

  const showToast = useCallback((m) => { setToast(m); setTimeout(() => setToast(null), 2800); }, []);

  const refreshWallet = useCallback(async () => {
    try { setWallet(await api.wallet()); } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    (async () => {
      if (getToken()) {
        try {
          const me = await api.me();
          setUser(me.user); setWallet(me.wallet); setAuthed(true);
        } catch { setToken(null); }
      }
      setReady(true);
    })();
  }, []);

  // Keep the wallet fresh (covers admin resolves/cash-outs done outside this tab).
  useEffect(() => {
    if (!authed) return;
    const t = setInterval(() => { api.wallet().then(setWallet).catch(() => {}); }, 5000);
    return () => clearInterval(t);
  }, [authed]);

  const onAuthed = (res) => { setUser(res.user); setWallet(res.wallet); setAuthed(true); };
  const logout = () => { setToken(null); setAuthed(false); setUser(null); };

  // Simple routing: /admin is the operator console (no user login required).
  if (window.location.pathname.replace(/\/+$/, "") === "/admin") return <AdminPage />;
  if (!ready) return <div style={{ background: C.bgPage, minHeight: "100vh" }} />;
  if (!authed) return <Login onAuthed={onAuthed} />;

  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh",
      background: C.bgPage, fontFamily: "system-ui,-apple-system,sans-serif", color: C.textPrimary }}>
      <style>{`
        * { box-sizing: border-box; }
        ::placeholder { color: ${C.textMuted}; }
        button:hover:not(:disabled) { filter: brightness(1.1); }
        button:active:not(:disabled) { transform: scale(0.97); }
        option { background: #1a1d27; color: #e8eaf0; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-thumb { background: #2a2d3e; border-radius: 3px; }
      `}</style>

      <header style={{ background: C.bgSidebar, borderBottom: `1px solid ${C.border}`, height: 52,
        display: "flex", alignItems: "center", padding: "0 20px", flexShrink: 0,
        position: "sticky", top: 0, zIndex: 100 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
          <div style={{ width: 28, height: 28, borderRadius: 8, background: C.accent, display: "flex",
            alignItems: "center", justifyContent: "center", fontSize: 15 }}>🎰</div>
          <span style={{ fontWeight: 800, fontSize: 16, letterSpacing: "-0.4px" }}>
            Kal<span style={{ color: C.accent }}>shady</span>
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, background: C.bgCard,
            border: `1px solid ${C.border}`, borderRadius: 8, padding: "6px 12px" }}>
            <span style={{ fontSize: 11, color: C.textMuted, textTransform: "uppercase", letterSpacing: 0.5 }}>Balance</span>
            <span style={{ fontSize: 14, fontWeight: 700 }}>{wallet.balance_display} SB</span>
          </div>
          <button onClick={() => setShowDeposit(true)} style={{ background: C.greenDim, color: C.green,
            border: `1px solid ${C.greenBorder}`, borderRadius: 8, padding: "6px 14px", fontSize: 12,
            fontWeight: 700, cursor: "pointer" }}>+ Deposit</button>
          <button onClick={logout} title={user?.name} style={{ background: "none", color: C.textMuted,
            border: `1px solid ${C.border}`, borderRadius: 8, padding: "6px 12px", fontSize: 12, cursor: "pointer" }}>
            Sign out
          </button>
        </div>
      </header>

      <main style={{ flex: 1, overflowY: "auto", minWidth: 0 }}>
        <MarketsPage wallet={wallet} refreshWallet={refreshWallet} showToast={showToast} />
      </main>

      <Toast msg={toast} />
      {showDeposit && <DepositModal onClose={() => setShowDeposit(false)}
        onDone={(w) => setWallet(w)} showToast={showToast} />}
    </div>
  );
}
