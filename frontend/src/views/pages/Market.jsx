import { useState, useEffect, useCallback } from "react";
import { C, SORT_OPTS } from '../../App.jsx';
import BetCard from '../components/BetCard.jsx';
import { api } from '../../api.js';

const pick = (outcomes, label, idx) =>
  outcomes.find(o => o.label.toLowerCase() === label) || outcomes[idx] || outcomes[0];

/* ─── MARKETS PAGE ─── */
function MarketsPage({ wallet, refreshWallet, showToast }) {
  const [markets, setMarkets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("newest"); // stable order: betting won't reshuffle the cards
  const [stake, setStake] = useState(100);
  const [placing, setPlacing] = useState(false);

  const load = useCallback(async () => {
    try { setMarkets(await api.markets()); } catch (e) { showToast(`❌ ${e.message}`); }
    finally { setLoading(false); }
  }, [showToast]);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000); // live odds/pool updates
    return () => clearInterval(t);
  }, [load]);

  const handleBet = async (market, side) => {
    if (placing) return;
    const outcome = side === "YES" ? pick(market.outcomes, "yes", 0) : pick(market.outcomes, "no", 1);
    const stake_cents = Math.round(Number(stake) * 100);
    if (stake_cents < 1000) { showToast("❌ Minimum bet is 10 SB."); return; }
    if (stake_cents > wallet.balance_cents) { showToast("❌ Not enough ShadyBucks — deposit first."); return; }
    setPlacing(true);
    try {
      await api.bet(market.id, outcome.id, stake_cents);
      showToast(`✅ Bet ${stake} SB on "${outcome.label}"`);
      await Promise.all([load(), refreshWallet()]);
    } catch (e) {
      showToast(`❌ ${e.message}`);
    } finally {
      setPlacing(false);
    }
  };

  // map backend markets -> card view models
  const cards = markets.map((m, i) => {
    const yes = pick(m.outcomes, "yes", 0);
    const no = pick(m.outcomes, "no", 1);
    return {
      raw: m, id: m.id, seed: i + 1,
      title: m.title,
      subtitle: `${m.status} · ${(m.total_pool_cents / 100).toFixed(0)} SB pool`,
      yes: yes ? yes.price_cents : 50,
      no: no ? no.price_cents : 50,
      open: m.status === "OPEN",
      volume: m.total_pool_cents,
    };
  });

  let list = cards.filter(c => {
    const q = search.toLowerCase();
    return !q || c.title.toLowerCase().includes(q);
  }).sort((a, b) => {
    if (sort === "volume") return b.volume - a.volume;
    if (sort === "certain") return Math.abs(b.yes - 50) - Math.abs(a.yes - 50);
    return 0; // newest: backend already returns newest-first
  });

  const totalVol = cards.reduce((s, c) => s + c.volume, 0);

  return (
    <>
      {/* sticky top bar */}
      <div style={{ position: "sticky", top: 0, zIndex: 50, background: C.bgPage,
        borderBottom: `1px solid ${C.border}`, padding: "12px 24px",
        display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ flex: 1, display: "flex", alignItems: "center", gap: 8, background: C.bgInput,
          border: `1px solid ${C.border}`, borderRadius: 8, padding: "8px 12px" }}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <circle cx="7" cy="7" r="5" stroke={C.textMuted} strokeWidth="1.5" />
            <path d="M11 11l3 3" stroke={C.textMuted} strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input type="text" placeholder="Search markets" value={search} onChange={e => setSearch(e.target.value)}
            style={{ background: "none", border: "none", outline: "none", fontSize: 13, color: C.textPrimary, width: "100%" }} />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, background: C.bgInput,
          border: `1px solid ${C.border}`, borderRadius: 8, padding: "4px 10px" }}>
          <span style={{ fontSize: 12, color: C.textMuted }}>Stake</span>
          <input type="number" min="10" step="10" value={stake} onChange={e => setStake(e.target.value)}
            style={{ width: 56, background: "none", border: "none", outline: "none", color: C.textPrimary, fontSize: 13, fontWeight: 600 }} />
          <span style={{ fontSize: 12, color: C.textMuted }}>SB</span>
        </div>
        <select value={sort} onChange={e => setSort(e.target.value)}
          style={{ background: C.bgInput, border: `1px solid ${C.border}`, color: C.textSecondary,
            borderRadius: 8, padding: "8px 12px", fontSize: 13, cursor: "pointer", outline: "none" }}>
          {SORT_OPTS.map(o => <option key={o.val} value={o.val}>{o.label}</option>)}
        </select>
      </div>

      <div style={{ padding: "20px 24px" }}>
        <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 10,
          padding: "12px 18px", display: "flex", gap: 28, marginBottom: 20, flexWrap: "wrap" }}>
          {[
            { label: "Total pool", val: `${(totalVol / 100).toFixed(0)} SB` },
            { label: "Open markets", val: cards.filter(c => c.open).length },
            { label: "Your balance", val: `${wallet.balance_display} SB` },
          ].map(s => (
            <div key={s.label}>
              <p style={{ margin: "0 0 2px", fontSize: 11, color: C.textMuted }}>{s.label}</p>
              <p style={{ margin: 0, fontSize: 16, fontWeight: 700, color: C.textPrimary }}>{s.val}</p>
            </div>
          ))}
        </div>

        {loading ? (
          <div style={{ textAlign: "center", padding: "60px 0", color: C.textMuted }}>Loading markets…</div>
        ) : list.length === 0 ? (
          <div style={{ textAlign: "center", padding: "60px 0", color: C.textMuted }}>
            <div style={{ fontSize: 36, marginBottom: 10 }}>🔮</div>
            <p style={{ margin: 0 }}>No markets yet.</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {list.map(b => <BetCard key={b.id} bet={b} onBet={handleBet} disabled={placing || !b.open} />)}
          </div>
        )}
      </div>
    </>
  );
}

export default MarketsPage;
