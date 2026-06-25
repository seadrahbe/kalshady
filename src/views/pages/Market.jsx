import { useState } from "react";
import { BETS, C, SORT_OPTS, CATEGORIES } from '../../App.jsx';
import BetCard from '../components/BetCard.jsx';
import Toast from '../components/Toast.jsx';

/* ─── MARKETS PAGE ─── */
function MarketsPage({ balance, setBalance }) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("volume");
  const [cat, setCat] = useState("all");
  const [toast, setToast] = useState(null);

  const showToast = (m) => { setToast(m); setTimeout(() => setToast(null), 2800); };

  const handleBet = (bet, side) => {
    if (balance < 1) { showToast("❌ Not enough ShadyBucks."); return; }
    setBalance(b => b - 1);
    const p = side === "YES" ? bet.yes / 100 : (100 - bet.yes) / 100;
    const won = Math.random() < p;
    if (won) { setBalance(b => b + 2); showToast(`✅ You won 1 ShadyBuck on "${bet.title.slice(0, 36)}…"`); }
    else showToast(`❌ Lost 1 ShadyBuck on "${bet.title.slice(0, 36)}…"`);
  };

  let list = BETS.filter(b => {
    const q = search.toLowerCase();
    return (cat === "all" || b.category === cat) &&
      (!q || b.title.toLowerCase().includes(q));
  }).sort((a, b2) => {
    if (sort === "volume") return b2.volume - a.volume;
    if (sort === "trending") return (b2.trending ? 1 : 0) - (a.trending ? 1 : 0) || b2.volume - a.volume;
    if (sort === "hot") return (b2.hot ? 1 : 0) - (a.hot ? 1 : 0) || b2.volume - a.volume;
    if (sort === "certain") return Math.abs(b2.yes - 50) - Math.abs(a.yes - 50);
    return 0;
  });

  return (
    <>
      <Toast msg={toast} />
      {/* sticky top bar */}
      <div style={{
        position: "sticky", top: 0, zIndex: 50,
        background: C.bgPage,
        borderBottom: `1px solid ${C.border}`,
        padding: "12px 24px",
        display: "flex", alignItems: "center", gap: 10,
      }}>
        <div style={{
          flex: 1, display: "flex", alignItems: "center", gap: 8,
          background: C.bgInput, border: `1px solid ${C.border}`,
          borderRadius: 8, padding: "8px 12px",
        }}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <circle cx="7" cy="7" r="5" stroke={C.textMuted} strokeWidth="1.5" />
            <path d="M11 11l3 3" stroke={C.textMuted} strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            placeholder="Search markets"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{
              background: "none", border: "none", outline: "none",
              fontSize: 13, color: C.textPrimary, width: "100%",
            }}
          />
          {search && <button onClick={() => setSearch("")} style={{ background: "none", border: "none", color: C.textMuted, cursor: "pointer", fontSize: 16, padding: 0, lineHeight: 1 }}>×</button>}
        </div>
        <select
          value={sort}
          onChange={e => setSort(e.target.value)}
          style={{
            background: C.bgInput, border: `1px solid ${C.border}`,
            color: C.textSecondary, borderRadius: 8, padding: "8px 12px",
            fontSize: 13, cursor: "pointer", outline: "none",
          }}
        >
          {SORT_OPTS.map(o => <option key={o.val} value={o.val}>{o.label}</option>)}
        </select>
      </div>

      <div style={{ padding: "20px 24px" }}>
        {/* category pills */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 20 }}>
          {CATEGORIES.map(c => (
            <button
              key={c.id}
              onClick={() => setCat(c.id)}
              style={{
                background: cat === c.id ? C.accentDim : C.bgCard,
                border: `1px solid ${cat === c.id ? C.accent : C.border}`,
                color: cat === c.id ? "#818cf8" : C.textSecondary,
                borderRadius: 20, padding: "6px 14px",
                fontSize: 12, fontWeight: 500, cursor: "pointer",
                display: "flex", alignItems: "center", gap: 6,
              }}
            >
              <span>{c.icon}</span> {c.label}
            </button>
          ))}
        </div>

        {/* volume banner */}
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`,
          borderRadius: 10, padding: "12px 18px",
          display: "flex", gap: 28, marginBottom: 20, flexWrap: "wrap",
        }}>
          {[
            { label: "24h volume", val: "$842K" },
            { label: "Open markets", val: list.length },
            { label: "Active traders", val: "14.2K" },
            { label: "Your balance", val: `${balance} SB` },
          ].map(s => (
            <div key={s.label}>
              <p style={{ margin: "0 0 2px", fontSize: 11, color: C.textMuted }}>{s.label}</p>
              <p style={{ margin: 0, fontSize: 16, fontWeight: 700, color: C.textPrimary }}>{s.val}</p>
            </div>
          ))}
        </div>

        {list.length === 0 ? (
          <div style={{ textAlign: "center", padding: "60px 0", color: C.textMuted }}>
            <div style={{ fontSize: 36, marginBottom: 10 }}>🔮</div>
            <p style={{ margin: 0 }}>No markets found.</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {list.map(b => <BetCard key={b.id} bet={b} onBet={handleBet} />)}
          </div>
        )}
      </div>
    </>
  );
}

export default MarketsPage;