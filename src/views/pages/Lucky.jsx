import { useState, useRef, useEffect, useCallback } from "react";

/* ─── PALETTE (Kalshi-faithful) ─── */
export const C = {
  bgPage: "#0f1117",
  bgSidebar: "#13151c",
  bgCard: "#1a1d27",
  bgCardHover: "#1f2235",
  bgInput: "#1a1d27",
  border: "#2a2d3e",
  borderLight: "#33374f",
  textPrimary: "#e8eaf0",
  textSecondary: "#8b90a8",
  textMuted: "#5a5f7a",
  green: "#00c076",
  greenDim: "rgba(0,192,118,0.12)",
  greenBorder: "rgba(0,192,118,0.3)",
  red: "#f03d3d",
  redDim: "rgba(240,61,61,0.12)",
  redBorder: "rgba(240,61,61,0.3)",
  accent: "#5b6af0",
  accentDim: "rgba(91,106,240,0.15)",
  yellow: "#f5c842",
  purple: "#9b72f5",
};

const WHEEL_SECTIONS = [
  { label: "Nothing", color: "#1e2235", textColor: C.textMuted, payout: 0 },
  { label: "Nothing", color: "#181b29", textColor: C.textMuted, payout: 0 },
  { label: "+1 SB", color: "#0d2e4a", textColor: "#4db8ff", payout: 1 },
  { label: "Nothing", color: "#1e2235", textColor: C.textMuted, payout: 0 },
  { label: "Nothing", color: "#181b29", textColor: C.textMuted, payout: 0 },
  { label: "🎉 +20!", color: "#2d1f5e", textColor: "#c4b5fd", payout: 20 },
  { label: "Nothing", color: "#1e2235", textColor: C.textMuted, payout: 0 },
  { label: "+1 SB", color: "#0d2e4a", textColor: "#4db8ff", payout: 1 },
  { label: "Nothing", color: "#181b29", textColor: C.textMuted, payout: 0 },
  { label: "Nothing", color: "#1e2235", textColor: C.textMuted, payout: 0 },
];


/* ─── LUCKY WHEEL ─── */
function LuckyPage({ balance, setBalance }) {
  const canvasRef = useRef(null);
  const totalRot = useRef(0);
  const [spinning, setSpinning] = useState(false);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const COST = 2;
  const N = WHEEL_SECTIONS.length;
  const slice = (2 * Math.PI) / N;

  const draw = useCallback((deg) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const S = canvas.width;
    const cx = S / 2, cy = S / 2, r = S / 2 - 8;
    ctx.clearRect(0, 0, S, S);
    const off = (deg * Math.PI) / 180;
    WHEEL_SECTIONS.forEach((sec, i) => {
      const a0 = off + i * slice - Math.PI / 2;
      const a1 = a0 + slice;
      ctx.beginPath(); ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, r, a0, a1); ctx.closePath();
      ctx.fillStyle = sec.color; ctx.fill();
      ctx.strokeStyle = "#0f1117"; ctx.lineWidth = 2; ctx.stroke();
      ctx.save(); ctx.translate(cx, cy);
      ctx.rotate(a0 + slice / 2);
      ctx.textAlign = "right";
      ctx.fillStyle = sec.textColor;
      ctx.font = `${sec.payout === 20 ? "bold 11px" : "500 11px"} system-ui,sans-serif`;
      ctx.fillText(sec.label, r - 10, 4);
      ctx.restore();
    });
    // hub
    ctx.beginPath(); ctx.arc(cx, cy, 20, 0, 2 * Math.PI);
    ctx.fillStyle = "#0f1117"; ctx.fill();
    ctx.strokeStyle = C.border; ctx.lineWidth = 2; ctx.stroke();
    ctx.beginPath(); ctx.arc(cx, cy, 8, 0, 2 * Math.PI);
    ctx.fillStyle = C.accent; ctx.fill();
  }, [slice]);

  useEffect(() => { draw(0); }, [draw]);

  const spin = () => {
    if (spinning || balance < COST) return;
    setBalance(b => b - COST);
    setResult(null); setSpinning(true);
    const winIdx = Math.random() < 0.05 ? 5 : Math.floor(Math.random() * N);
    const spins = 5 + Math.floor(Math.random() * 4);
    const end = totalRot.current + 360 * spins + (360 - winIdx * (360 / N)) - (360 / N) / 2;
    const start = totalRot.current, dur = 4200, t0 = performance.now();
    const tick = (now) => {
      const t = Math.min((now - t0) / dur, 1);
      const e = 1 - Math.pow(1 - t, 4);
      const cur = start + (end - start) * e;
      totalRot.current = cur;
      draw(cur % 360);
      if (t < 1) { requestAnimationFrame(tick); return; }
      setSpinning(false);
      const sec = WHEEL_SECTIONS[winIdx];
      setResult({ sec, idx: winIdx });
      if (sec.payout > 0) setBalance(b => b + sec.payout);
      setHistory(h => [{ sec, t: new Date().toLocaleTimeString() }, ...h.slice(0, 9)]);
    };
    requestAnimationFrame(tick);
  };

  return (
    <div style={{ padding: "24px", maxWidth: 560 }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ margin: "0 0 4px", fontSize: 20, fontWeight: 700, color: C.textPrimary }}>Feeling Lucky?</h2>
        <p style={{ margin: 0, fontSize: 13, color: C.textMuted }}>−{COST} ShadyBucks per spin. Probably nothing.</p>
      </div>

      <div style={{
        background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14,
        padding: "28px 24px", marginBottom: 16,
        display: "flex", flexDirection: "column", alignItems: "center", gap: 20,
      }}>
        <div style={{ position: "relative" }}>
          <canvas ref={canvasRef} width={280} height={280}
            style={{ display: "block", borderRadius: "50%", border: `3px solid ${C.border}` }}
            role="img" aria-label="Spinning prize wheel with 10 sections" />
          {/* pointer */}
          <div style={{
            position: "absolute", top: "50%", right: -20,
            transform: "translateY(-50%)",
            width: 0, height: 0,
            borderTop: "10px solid transparent",
            borderBottom: "10px solid transparent",
            borderRight: `20px solid ${C.yellow}`,
          }} />
        </div>

        {result && (
          <div style={{
            background: result.sec.payout > 0 ? "rgba(155,114,245,0.1)" : "rgba(255,255,255,0.03)",
            border: `1px solid ${result.sec.payout > 0 ? C.purple : C.border}`,
            borderRadius: 10, padding: "12px 20px", textAlign: "center", width: "100%",
          }}>
            <p style={{
              margin: 0, fontWeight: 600, fontSize: result.sec.payout === 20 ? 18 : 14,
              color: result.sec.payout === 20 ? C.purple : result.sec.payout === 1 ? "#4db8ff" : C.textMuted,
            }}>
              {result.sec.payout === 20 ? "🎉 Jackpot! +20 ShadyBucks" :
               result.sec.payout === 1 ? "+1 ShadyBuck. A moral victory." :
               "Nothing. The wheel is indifferent to your suffering."}
            </p>
          </div>
        )}

        <button onClick={spin} disabled={spinning || balance < COST}
          style={{
            background: spinning || balance < COST ? C.bgInput : C.accent,
            color: spinning || balance < COST ? C.textMuted : "#fff",
            border: `1px solid ${spinning || balance < COST ? C.border : C.accent}`,
            borderRadius: 8, padding: "12px 36px",
            fontSize: 14, fontWeight: 700, cursor: spinning || balance < COST ? "not-allowed" : "pointer",
            width: "100%", letterSpacing: 0.3,
          }}>
          {spinning ? "Spinning…" : balance < COST ? "Need 2 ShadyBucks to spin" : `Spin the wheel  −${COST} SB`}
        </button>

        <p style={{ margin: 0, fontSize: 11, color: C.textMuted, textAlign: "center" }}>
          Jackpot probability: ~5% &nbsp;·&nbsp; +1 SB probability: 20% &nbsp;·&nbsp; Nothing: 75%
        </p>
      </div>

      {history.length > 0 && (
        <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 10, overflow: "hidden" }}>
          <div style={{ padding: "10px 16px", borderBottom: `1px solid ${C.border}` }}>
            <p style={{ margin: 0, fontSize: 12, fontWeight: 600, color: C.textSecondary, textTransform: "uppercase", letterSpacing: 0.5 }}>
              Recent spins
            </p>
          </div>
          {history.map((h, i) => (
            <div key={i} style={{
              padding: "9px 16px",
              borderBottom: i < history.length - 1 ? `1px solid ${C.border}` : "none",
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <span style={{ fontSize: 13, color: h.sec.payout === 20 ? C.purple : h.sec.payout === 1 ? "#4db8ff" : C.textMuted }}>
                {h.sec.payout === 20 ? "🎉 +20 SB — Jackpot!" : h.sec.payout === 1 ? "+1 SB" : "Nothing"}
              </span>
              <span style={{ fontSize: 11, color: C.textMuted }}>{h.t}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default LuckyPage;