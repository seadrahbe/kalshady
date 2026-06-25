import { useState } from "react";
import { C } from '../../App.jsx';
import Sparkline from './SparkLine.jsx';

/* ─── BET CARD ─── */
function BetCard({ bet, onBet, disabled }) {
  const [hov, setHov] = useState(false);
  const yes = bet.yes;
  const no = bet.no ?? (100 - bet.yes);
  const yesColor = C.green;
  const noColor = C.red;
  const buy = (side) => () => !disabled && onBet(bet.raw, side);

  const buyBtn = (label, color, dim, border, side) => (
    <button onClick={buy(side)} disabled={disabled}
      style={{
        background: dim, color, border: `1px solid ${border}`, borderRadius: 6,
        padding: "5px 12px", fontSize: 12, fontWeight: 700, letterSpacing: 0.3,
        cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.45 : 1,
      }}>
      {label}
    </button>
  );

  return (
    <div onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{
        background: hov ? C.bgCardHover : C.bgCard,
        border: `1px solid ${hov ? C.borderLight : C.border}`,
        borderRadius: 12, padding: "16px 18px",
        transition: "background 0.15s, border-color 0.15s",
        display: "flex", flexDirection: "column", gap: 12,
      }}>
      {/* header row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 500, color: C.textPrimary, lineHeight: 1.4 }}>
            {bet.title}
          </p>
          <p style={{ margin: 0, fontSize: 11, color: C.textMuted }}>{bet.subtitle}</p>
        </div>
        <Sparkline yes={yes} id={bet.seed} />
      </div>

      {/* probability bar */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: yesColor }}>Yes {yes}¢</span>
          <span style={{ fontSize: 12, fontWeight: 600, color: noColor }}>No {no}¢</span>
        </div>
        <div style={{ height: 4, borderRadius: 99, background: "#252840", overflow: "hidden", position: "relative" }}>
          <div style={{ position: "absolute", inset: 0, right: `${100 - yes}%`, background: yesColor, borderRadius: "99px 0 0 99px" }} />
          <div style={{ position: "absolute", inset: 0, left: `${yes}%`, background: noColor, borderRadius: "0 99px 99px 0" }} />
        </div>
      </div>

      {/* stats row */}
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <span style={{ fontSize: 11, color: C.textMuted }}>
          <span style={{ color: C.textSecondary, fontWeight: 500 }}>{(bet.volume / 100).toFixed(0)} SB</span> pool
        </span>
        {!bet.open && (
          <span style={{ fontSize: 10, background: "rgba(255,255,255,0.06)", color: C.textMuted,
            padding: "2px 7px", borderRadius: 4, fontWeight: 600 }}>{bet.raw.status}</span>
        )}
        <div style={{ flex: 1 }} />
        {buyBtn("Buy Yes", C.green, C.greenDim, C.greenBorder, "YES")}
        {buyBtn("Buy No", C.red, C.redDim, C.redBorder, "NO")}
      </div>
    </div>
  );
}

export default BetCard;
