import { C } from '../../App.jsx';

/* ─── MINI SPARKLINE ─── */
function Sparkline({ yes, id, width = 80, height = 32 }) {
  const pts = Array.from({ length: 20 }, (_, i) => {
    const n = Math.sin(i * 0.7 + id) * 9 + Math.cos(i * 1.1 + id * 0.4) * 6;
    return Math.max(4, Math.min(96, yes + n));
  });
  const xs = pts.map((_, i) => (i / (pts.length - 1)) * width);
  const ys = pts.map(p => height - (p / 100) * height);
  const line = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
  const area = `${line} L${width},${height} L0,${height}Z`;
  const col = yes >= 50 ? C.green : C.red;
  const fill = yes >= 50 ? "rgba(0,192,118,0.08)" : "rgba(240,61,61,0.08)";
  return (
    <svg width={width} height={height} style={{ display: "block", flexShrink: 0 }} aria-hidden="true">
      <path d={area} fill={fill} />
      <path d={line} fill="none" stroke={col} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={xs[xs.length - 1]} cy={ys[ys.length - 1]} r="2.5" fill={col} />
    </svg>
  );
}

export default Sparkline;