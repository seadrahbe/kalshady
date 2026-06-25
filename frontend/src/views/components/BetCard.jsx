import { useState } from "react";
import { C } from '../../App.jsx';
import Sparkline from './SparkLine.jsx';

/* ─── BET CARD ─── */
function BetCard({ bet, onBet }) {
  const [hov, setHov] = useState(false);
  const no = 100 - bet.yes;
  const yesColor = C.green;
  const noColor = C.red;

  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        background: hov ? C.bgCardHover : C.bgCard,
        border: `1px solid ${hov ? C.borderLight : C.border}`,
        borderRadius: 12,
        padding: "16px 18px",
        cursor: "default",
        transition: "background 0.15s, border-color 0.15s",
        display: "flex",
        flexDirection: "column",
        gap: 12,
      }}
    >
      {/* header row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 500, color: C.textPrimary, lineHeight: 1.4 }}>
            {bet.title}
          </p>
          <p style={{ margin: 0, fontSize: 11, color: C.textMuted }}>{bet.subtitle}</p>
        </div>
        <Sparkline yes={bet.yes} id={bet.id} />
      </div>

      {/* probability bar */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: yesColor }}>Yes {bet.yes}¢</span>
          <span style={{ fontSize: 12, fontWeight: 600, color: noColor }}>No {no}¢</span>
        </div>
        <div style={{ height: 4, borderRadius: 99, background: "#252840", overflow: "hidden", position: "relative" }}>
          <div style={{ position: "absolute", inset: 0, right: `${no}%`, background: yesColor, borderRadius: "99px 0 0 99px" }} />
          <div style={{ position: "absolute", inset: 0, left: `${bet.yes}%`, background: noColor, borderRadius: "0 99px 99px 0" }} />
        </div>
      </div>

      {/* stats row */}
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <span style={{ fontSize: 11, color: C.textMuted }}>
          <span style={{ color: C.textSecondary, fontWeight: 500 }}>${(bet.volume / 1000).toFixed(0)}K</span> vol
        </span>
        <span style={{ fontSize: 11, color: C.textMuted }}>
          <span style={{ color: C.textSecondary, fontWeight: 500 }}>{bet.traders.toLocaleString()}</span> traders
        </span>
        {bet.hot && <span style={{ fontSize: 10, background: "rgba(245,200,66,0.12)", color: C.yellow, padding: "2px 7px", borderRadius: 4, fontWeight: 600 }}>HOT</span>}
        {bet.trending && <span style={{ fontSize: 10, background: C.accentDim, color: "#818cf8", padding: "2px 7px", borderRadius: 4, fontWeight: 600 }}>TRENDING</span>}
        <div style={{ flex: 1 }} />
        <button
          onClick={() => onBet(bet, "YES")}
          style={{
            background: C.greenDim,
            color: C.green,
            border: `1px solid ${C.greenBorder}`,
            borderRadius: 6,
            padding: "5px 12px",
            fontSize: 12,
            fontWeight: 700,
            cursor: "pointer",
            letterSpacing: 0.3,
          }}
        >
          Buy Yes
        </button>
        <button
          onClick={() => onBet(bet, "NO")}
          style={{
            background: C.redDim,
            color: C.red,
            border: `1px solid ${C.redBorder}`,
            borderRadius: 6,
            padding: "5px 12px",
            fontSize: 12,
            fontWeight: 700,
            cursor: "pointer",
            letterSpacing: 0.3,
          }}
        >
          Buy No
        </button>
      </div>
    </div>
  );
}

export default BetCard;