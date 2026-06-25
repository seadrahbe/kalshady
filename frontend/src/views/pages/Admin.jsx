import { useState, useEffect, useCallback } from "react";
import { C } from '../../App.jsx';
import { api, admin, getAdminKey, setAdminKey } from '../../api.js';

// NOTE: styles that read C must NOT be module-level — App.jsx (which exports C) is still
// initializing when it imports this module, so C would be in the temporal dead zone.
const btn = (bg, col, bd) => ({ background: bg, color: col, border: `1px solid ${bd}`, borderRadius: 8,
  padding: "7px 12px", fontSize: 12, fontWeight: 700, cursor: "pointer" });
const yesId = (m) => (m.outcomes.find(o => o.label === "Yes") || m.outcomes[0]).id;
const noId = (m) => (m.outcomes.find(o => o.label === "No") || m.outcomes[1]).id;
const price = (m, label) => (m.outcomes.find(o => o.label === label) || {}).price_cents ?? 50;

export default function AdminPage() {
  const box = { background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 12, padding: 18 };
  const input = { background: C.bgInput, border: `1px solid ${C.border}`, color: C.textPrimary,
    borderRadius: 8, padding: "9px 11px", fontSize: 14, outline: "none" };

  const [unlocked, setUnlocked] = useState(false);
  const [pw, setPw] = useState("");
  const [markets, setMarkets] = useState([]);
  const [msg, setMsg] = useState(null);
  const [title, setTitle] = useState("");
  const [yes, setYes] = useState(50);
  const [otp, setOtp] = useState("");
  const [odds, setOdds] = useState({}); // marketId -> edited Yes price

  const show = (m) => { setMsg(m); setTimeout(() => setMsg(null), 2600); };
  const load = useCallback(async () => { try { setMarkets(await api.markets()); } catch (e) { show("❌ " + e.message); } }, []);
  useEffect(() => { load(); }, [load]);

  // Auto-unlock if a previously-saved key still validates.
  useEffect(() => {
    if (getAdminKey()) admin.check().then(() => setUnlocked(true)).catch(() => {});
  }, []);

  const unlock = async (e) => {
    e.preventDefault();
    setAdminKey(pw.trim());
    try { await admin.check(); setUnlocked(true); setMsg(null); }
    catch { setAdminKey(""); show("❌ Wrong password"); }
  };
  const lock = () => { setAdminKey(""); setUnlocked(false); setPw(""); };

  const wrap = (fn) => async (...a) => { try { await fn(...a); } catch (e) { show("❌ " + e.message); } };

  const create = wrap(async (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    const y = Math.max(1, Math.min(99, Number(yes)));
    await admin.createMarket(title.trim(), ["Yes", "No"], [y, 100 - y]);
    setTitle(""); setYes(50); show("✅ Market created"); load();
  });
  const saveOdds = wrap(async (m) => {
    const y = Math.max(0, Math.min(100, Number(odds[m.id] ?? price(m, "Yes"))));
    await admin.setOdds(m.id, { [yesId(m)]: y, [noId(m)]: 100 - y });
    show("✅ Odds updated"); load();
  });
  const resolve = wrap(async (m, oid) => { await admin.resolve(m.id, oid); show("✅ Resolved"); load(); });
  const voidM = wrap(async (m) => { await admin.voidMarket(m.id); show("✅ Voided"); load(); });
  const cashout = wrap(async () => {
    const r = await admin.cashout(otp.trim() || null);
    show(`✅ Cashed out ${r.sent_count} wallet(s), ${r.sent_display} SB${r.failed_count ? ` — ${r.failed_count} failed` : ""}`);
  });

  if (!unlocked) {
    return (
      <div style={{ minHeight: "100vh", background: C.bgPage, display: "flex", alignItems: "center",
        justifyContent: "center", fontFamily: "system-ui,-apple-system,sans-serif", color: C.textPrimary }}>
        <form onSubmit={unlock} style={{ ...box, width: 320, display: "flex", flexDirection: "column", gap: 12 }}>
          <p style={{ margin: 0, fontWeight: 800, fontSize: 16 }}>Kal<span style={{ color: C.accent }}>shady</span> · Admin</p>
          <p style={{ margin: 0, fontSize: 12, color: C.textMuted }}>Enter the admin password.</p>
          <input style={input} type="password" autoFocus placeholder="Password" value={pw}
            onChange={e => setPw(e.target.value)} />
          <button style={btn(C.accent, "#fff", C.accent)}>Unlock</button>
          {msg && <p style={{ margin: 0, color: C.red, fontSize: 12 }}>{msg}</p>}
        </form>
      </div>
    );
  }

  return (
    <div style={{ minHeight: "100vh", background: C.bgPage, color: C.textPrimary,
      fontFamily: "system-ui,-apple-system,sans-serif", padding: "24px", maxWidth: 860, margin: "0 auto" }}>
      <style>{`::placeholder{color:${C.textMuted}} option{background:#1a1d27;color:#e8eaf0}`}</style>
      <h1 style={{ fontSize: 20, fontWeight: 800, margin: "0 0 4px" }}>
        Kal<span style={{ color: C.accent }}>shady</span> · Admin
      </h1>
      <p style={{ color: C.textMuted, fontSize: 12, margin: "0 0 18px", display: "flex", gap: 14 }}>
        <a href="/" style={{ color: C.accent }}>← back to markets</a>
        <a onClick={lock} style={{ color: C.textMuted, cursor: "pointer" }}>lock</a>
      </p>

      {/* create market */}
      <form onSubmit={create} style={{ ...box, marginBottom: 14, display: "flex", flexDirection: "column", gap: 10 }}>
        <p style={{ margin: 0, fontWeight: 700, fontSize: 14 }}>New question</p>
        <input style={input} placeholder="Question, e.g. Will it rain on Saturday?" value={title}
          onChange={e => setTitle(e.target.value)} />
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 12, color: C.textMuted }}>Yes odds</span>
          <input style={{ ...input, width: 80 }} type="number" min="1" max="99" value={yes}
            onChange={e => setYes(e.target.value)} />
          <span style={{ fontSize: 12, color: C.green }}>Yes {yes}¢</span>
          <span style={{ fontSize: 12, color: C.red }}>No {100 - yes}¢</span>
          <div style={{ flex: 1 }} />
          <button type="submit" style={btn(C.accent, "#fff", C.accent)}>Create (30% rake)</button>
        </div>
      </form>

      {/* cash out */}
      <div style={{ ...box, marginBottom: 20, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <p style={{ margin: 0, fontWeight: 700, fontSize: 14, minWidth: 160 }}>End-of-event cash-out</p>
        <input style={{ ...input, flex: 1, minWidth: 160 }} placeholder="House OTP (live bank)" value={otp}
          onChange={e => setOtp(e.target.value)} />
        <button style={btn(C.greenDim, C.green, C.greenBorder)} onClick={cashout}>Pay everyone out</button>
      </div>

      {/* markets */}
      <p style={{ fontSize: 12, color: C.textMuted, textTransform: "uppercase", letterSpacing: 1, margin: "0 0 8px" }}>Markets</p>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {markets.map(m => (
          <div key={m.id} style={{ ...box, display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
              <span style={{ fontSize: 14, fontWeight: 600 }}>{m.title}</span>
              <span style={{ fontSize: 11, color: C.textMuted }}>{m.status} · {(m.total_pool_cents / 100).toFixed(0)} SB pool</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, color: C.green }}>Yes {price(m, "Yes")}¢</span>
              <span style={{ fontSize: 12, color: C.red }}>No {price(m, "No")}¢</span>
              <span style={{ width: 12 }} />
              <span style={{ fontSize: 11, color: C.textMuted }}>set Yes</span>
              <input style={{ ...input, width: 64, padding: "5px 8px" }} type="number" min="0" max="100"
                value={odds[m.id] ?? price(m, "Yes")} onChange={e => setOdds({ ...odds, [m.id]: e.target.value })} />
              <button style={btn(C.bgInput, C.textSecondary, C.border)} onClick={() => saveOdds(m)}>Set odds</button>
              <div style={{ flex: 1 }} />
              {(m.status === "OPEN" || m.status === "CLOSED") && (
                <>
                  <button style={btn(C.greenDim, C.green, C.greenBorder)} onClick={() => resolve(m, yesId(m))}>Yes wins</button>
                  <button style={btn(C.redDim, C.red, C.redBorder)} onClick={() => resolve(m, noId(m))}>No wins</button>
                  <button style={btn(C.bgInput, C.textMuted, C.border)} onClick={() => voidM(m)}>Void</button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      {msg && (
        <div style={{ position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)",
          background: C.bgCard, border: `1px solid ${C.border}`, color: C.textPrimary,
          padding: "10px 20px", borderRadius: 10, fontSize: 13 }}>{msg}</div>
      )}
    </div>
  );
}
