import logo from './logo.svg';
import './App.css';
import LuckyPage from './views/pages/Lucky.jsx';
import MarketsPage from './views/pages/Market.jsx';

import { useState } from "react";

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

/* ─── DATA ─── */
export const CATEGORIES = [
  { id: "all", label: "All markets", icon: "▦" },
  { id: "toorcamp", label: "ToorCamp", icon: "👾" },
  { id: "weather", label: "Weather", icon: "🌡️" },
  { id: "finance", label: "Economics", icon: "📈" },
  { id: "tech", label: "Tech", icon: "💻" },
  { id: "sports", label: "Sports", icon: "⚽" },
  { id: "science", label: "Science", icon: "🔬" },
  { id: "culture", label: "Culture", icon: "🎬" },
];

export const BETS = [
  {
    id: 1, category: "weather",
    title: "Will it rain on June 26th?",
    subtitle: "Closes 12AM June 26th, 2025",
    yes: 3, volume: 142800, liquidity: 28400, traders: 3812,
    hot: true, trending: false,
  },
  {
    id: 2, category: "finance",
    title: "Will the S&P 500 beat a dart thrown at the WSJ?",
    subtitle: "Closes Dec 31, 2025",
    yes: 51, volume: 98400, liquidity: 19200, traders: 2241,
    hot: false, trending: true,
  },
  {
    id: 3, category: "tech",
    title: "Will Elon tweet something controversial this week?",
    subtitle: "Closes Sun, Jun 29",
    yes: 97, volume: 87600, liquidity: 14100, traders: 5509,
    hot: true, trending: true,
  },
  {
    id: 4, category: "culture",
    title: "Will a major airline lose your luggage at least once in 2025?",
    subtitle: "Closes Dec 31, 2025",
    yes: 82, volume: 76200, liquidity: 11000, traders: 1874,
    hot: false, trending: false,
  },
  {
    id: 5, category: "finance",
    title: "Will the Fed use the word 'transitory' again in 2025?",
    subtitle: "Closes Dec 31, 2025",
    yes: 44, volume: 63100, liquidity: 9800, traders: 1203,
    hot: false, trending: true,
  },
  {
    id: 6, category: "culture",
    title: "Will a hot dog be legally classified as a sandwich before 2030?",
    subtitle: "Closes Dec 31, 2029",
    yes: 19, volume: 55300, liquidity: 7400, traders: 988,
    hot: false, trending: false,
  },
  {
    id: 7, category: "sports",
    title: "Will a commentator say '110 percent' 10+ times in one game?",
    subtitle: "Closes Jun 30",
    yes: 76, volume: 48900, liquidity: 6200, traders: 741,
    hot: false, trending: false,
  },
  {
    id: 8, category: "tech",
    title: "Will AI replace the guy who makes the coffee wrong?",
    subtitle: "Closes Dec 31, 2026",
    yes: 31, volume: 42200, liquidity: 5100, traders: 634,
    hot: false, trending: true,
  },
  {
    id: 9, category: "science",
    title: "Will scientists discover a new planet and name it something boring?",
    subtitle: "Closes Dec 31, 2025",
    yes: 88, volume: 33700, liquidity: 4900, traders: 521,
    hot: false, trending: false,
  },
  {
    id: 10, category: "finance",
    title: "Will anyone be convicted for a crypto scam with a dog logo?",
    subtitle: "Closes Dec 31, 2025",
    yes: 62, volume: 29800, liquidity: 3800, traders: 447,
    hot: true, trending: false,
  },
  {
    id: 11, category: "science",
    title: "Will a 'once in a lifetime' weather event happen twice in one year?",
    subtitle: "Closes Dec 31, 2025",
    yes: 71, volume: 22100, liquidity: 2900, traders: 338,
    hot: false, trending: true,
  },
  {
    id: 12, category: "culture",
    title: "Will a celebrity chef claim to have 'invented' a 400-year-old dish?",
    subtitle: "Closes Dec 31, 2025",
    yes: 92, volume: 14400, liquidity: 2100, traders: 209,
    hot: false, trending: false,
  },
];

export const SORT_OPTS = [
  { val: "volume", label: "Most volume" },
  { val: "trending", label: "Trending" },
  { val: "hot", label: "Hot" },
  { val: "newest", label: "Newest" },
  { val: "certain", label: "Most certain" },
];

/* ─── ROOT APP ─── */
export default function App() {
  const [page, setPage] = useState("markets");
  const [balance, setBalance] = useState(10);

  const NAV = [
    { id: "markets", label: "Markets", icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <rect x="1" y="9" width="3" height="6" rx="1" fill="currentColor" opacity=".5"/>
        <rect x="6" y="5" width="3" height="10" rx="1" fill="currentColor"/>
        <rect x="11" y="1" width="3" height="14" rx="1" fill="currentColor" opacity=".7"/>
      </svg>
    )},
    { id: "lucky", label: "Feeling Lucky?", icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M5 8.5s.8 2 3 2 3-2 3-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        <circle cx="5.5" cy="6" r="1" fill="currentColor"/>
        <circle cx="10.5" cy="6" r="1" fill="currentColor"/>
      </svg>
    )},
  ];

  return (
    <div style={{
      display: "flex", flexDirection: "column", minHeight: "100vh",
      background: C.bgPage, fontFamily: "system-ui,-apple-system,sans-serif", color: C.textPrimary,
    }}>
      <style>{`
        * { box-sizing: border-box; }
        ::placeholder { color: ${C.textMuted}; }
        button { font-family: inherit; }
        button:hover:not(:disabled) { filter: brightness(1.1); }
        button:active:not(:disabled) { transform: scale(0.97); }
        input, select { font-family: inherit; }
        option { background: #1a1d27; color: #e8eaf0; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #2a2d3e; border-radius: 3px; }
      `}</style>

      {/* ── TOP NAV ── */}
      <header style={{
        background: C.bgSidebar, borderBottom: `1px solid ${C.border}`,
        height: 52, display: "flex", alignItems: "center",
        padding: "0 20px", gap: 0, flexShrink: 0,
        position: "sticky", top: 0, zIndex: 100,
      }}>
        {/* logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginRight: 28 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 8,
            background: C.accent, display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 15,
          }}>🎰</div>
          <span style={{ fontWeight: 800, fontSize: 16, color: C.textPrimary, letterSpacing: "-0.4px" }}>
            Kal<span style={{ color: C.accent }}>shady</span>
          </span>
        </div>

        {/* nav links */}
        <nav style={{ display: "flex", gap: 2, flex: 1 }}>
          {NAV.map(n => (
            <button key={n.id} onClick={() => setPage(n.id)}
              style={{
                display: "flex", alignItems: "center", gap: 7,
                background: "none", border: "none",
                color: page === n.id ? C.textPrimary : C.textMuted,
                fontWeight: page === n.id ? 600 : 400,
                padding: "0 12px", height: 52, fontSize: 13,
                cursor: "pointer",
                borderBottom: page === n.id ? `2px solid ${C.accent}` : "2px solid transparent",
                transition: "color 0.15s, border-color 0.15s",
              }}>
              {n.icon} {n.label}
            </button>
          ))}
        </nav>

        {/* balance */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 8,
            background: C.bgCard, border: `1px solid ${C.border}`,
            borderRadius: 8, padding: "6px 12px",
          }}>
            <span style={{ fontSize: 11, color: C.textMuted, textTransform: "uppercase", letterSpacing: 0.5 }}>Balance</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: C.textPrimary }}>{balance} SB</span>
          </div>
          {balance < 3 && (
            <button onClick={() => setBalance(b => b + 10)}
              style={{
                background: C.greenDim, color: C.green,
                border: `1px solid ${C.greenBorder}`,
                borderRadius: 8, padding: "6px 14px",
                fontSize: 12, fontWeight: 700, cursor: "pointer",
              }}>
              + Free SB
            </button>
          )}
        </div>
      </header>

      {/* ── BODY: sidebar + content ── */}
      <div style={{ display: "flex", flex: 1 }}>
        {/* sidebar */}
        <aside style={{
          width: 200, flexShrink: 0,
          background: C.bgSidebar,
          borderRight: `1px solid ${C.border}`,
          padding: "16px 0",
        }}>
          <p style={{ margin: "0 16px 8px", fontSize: 10, fontWeight: 700, color: C.textMuted, textTransform: "uppercase", letterSpacing: 1 }}>
            Categories
          </p>
          {CATEGORIES.map(c => (
            <button key={c.id} onClick={() => { setPage("markets"); }}
              style={{
                display: "flex", alignItems: "center", gap: 10,
                width: "100%", background: "none", border: "none",
                color: C.textSecondary, padding: "8px 16px",
                fontSize: 13, textAlign: "left", cursor: "pointer",
                transition: "color 0.1s, background 0.1s",
              }}
              onMouseEnter={e => { e.currentTarget.style.background = "rgba(255,255,255,0.04)"; e.currentTarget.style.color = C.textPrimary; }}
              onMouseLeave={e => { e.currentTarget.style.background = "none"; e.currentTarget.style.color = C.textSecondary; }}
            >
              <span style={{ fontSize: 14 }}>{c.icon}</span>
              {c.label}
            </button>
          ))}

          <div style={{ margin: "16px 0", borderTop: `1px solid ${C.border}` }} />

          <p style={{ margin: "0 16px 8px", fontSize: 10, fontWeight: 700, color: C.textMuted, textTransform: "uppercase", letterSpacing: 1 }}>
            Disclaimer
          </p>
          <p style={{ margin: "0 16px", fontSize: 11, color: C.textMuted, lineHeight: 1.5 }}>
            ShadyBucks™ are not real money. Kalshady is satire. Losses are spiritual.
          </p>
        </aside>

        {/* main content */}
        <main style={{ flex: 1, overflowY: "auto", minWidth: 0 }}>
          {page === "markets" && <MarketsPage balance={balance} setBalance={setBalance} />}
          {page === "lucky" && <LuckyPage balance={balance} setBalance={setBalance} />}
        </main>
      </div>
    </div>
  );
}