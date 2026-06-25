import { C } from '../../App.jsx';

/* ─── TOAST ─── */
function Toast({ msg }) {
  if (!msg) return null;
  const won = msg.startsWith("✅");
  return (
    <div style={{
      position: "fixed", bottom: 28, left: "50%", transform: "translateX(-50%)",
      background: won ? "#0d2e1e" : "#2a1010",
      border: `1px solid ${won ? C.greenBorder : C.redBorder}`,
      color: won ? C.green : C.red,
      padding: "11px 22px", borderRadius: 10, fontSize: 13, zIndex: 999,
      maxWidth: 420, textAlign: "center", whiteSpace: "nowrap",
    }}>{msg}</div>
  );
}

export default Toast;