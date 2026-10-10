const PATHS = {
  chat: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  dashboard: "M3 3h8v8H3zM13 3h8v5h-8zM13 10h8v11h-8zM3 13h8v8H3z",
  brain: "M12 2a4 4 0 0 0-4 4v1a3 3 0 0 0-3 3 3 3 0 0 0 1 2.2A3.5 3.5 0 0 0 8 18.9V19a3 3 0 0 0 4 2.8M12 2a4 4 0 0 1 4 4v1a3 3 0 0 1 3 3 3 3 0 0 1-1 2.2 3.5 3.5 0 0 1-2 6.7V19a3 3 0 0 1-4 2.8M12 2v20",
  book: "M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5zM4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5",
  send: "M22 2L11 13M22 2l-7 20-4-9-9-4z",
  ticket: "M3 9a2 2 0 0 0 0 6v3h18v-3a2 2 0 0 1 0-6V6H3z",
  check: "M20 6L9 17l-5-5",
  alert: "M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
  bolt: "M13 2L3 14h9l-1 8 10-12h-9z",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3",
  refresh: "M23 4v6h-6M1 20v-6h6M3.5 9a9 9 0 0 1 14.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0 0 20.5 15",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  db: "M12 8c4.4 0 8-1.3 8-3s-3.6-3-8-3-8 1.3-8 3 3.6 3 8 3zM4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  package: "M16.5 9.4l-9-5.2M21 16V8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 2 0l7-4a2 2 0 0 0 1-1.7zM3.3 7L12 12l8.7-5M12 22V12",
  spark: "M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z",
  file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6",
  x: "M18 6L6 18M6 6l12 12",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
};

export function Icon({ name, size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name] || PATHS.spark} />
    </svg>
  );
}

export function Pill({ tone = "neutral", icon, children }) {
  return (
    <span className={`pill ${tone}`}>
      {icon && <Icon name={icon} size={12} />}
      {children}
    </span>
  );
}

export function Avatar({ name = "?", tone = "primary" }) {
  const initials = name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  return <span className={`avatar ${tone}`}>{initials}</span>;
}

export function Confidence({ value = 0, threshold = 0.5, compact = false }) {
  const ok = value >= threshold;
  const pct = Math.round(value * 100);
  return (
    <div className={compact ? "conf compact" : "conf"}>
      <div className="conf-head">
        <span>AI confidence</span>
        <b className={ok ? "ok" : "bad"}>{pct}%</b>
      </div>
      <div className="conf-track">
        <div className={ok ? "conf-fill ok" : "conf-fill bad"} style={{ width: `${Math.max(pct, 2)}%` }} />
        <div className="conf-mark" style={{ left: `${Math.round(threshold * 100)}%` }} title="Escalation threshold" />
      </div>
      {!compact && <div className="conf-foot">Threshold {Math.round(threshold * 100)}% · {ok ? "answer allowed" : "below threshold, human escalation"}</div>}
    </div>
  );
}

const STATUS_TONE = { ok: "success", failed: "danger", warn: "warn", skipped: "neutral" };

export function Steps({ steps }) {
  return (
    <ol className="steps">
      {steps.map((s, i) => (
        <li key={i} className={`step ${s.status}`}>
          <span className="dot">{s.status === "ok" ? <Icon name="check" size={11} /> : s.status === "skipped" ? "–" : "!"}</span>
          <div>
            <div className="step-title">{s.step}<Pill tone={STATUS_TONE[s.status] || "neutral"}>{s.status}</Pill></div>
            <div className="step-detail">{s.detail}</div>
          </div>
        </li>
      ))}
    </ol>
  );
}

export function Donut({ segments, size = 150, label }) {
  const total = segments.reduce((a, s) => a + s.value, 0);
  const r = 52;
  const c = 2 * Math.PI * r;
  let offset = 0;
  return (
    <div className="donut">
      <svg width={size} height={size} viewBox="0 0 140 140">
        <circle cx="70" cy="70" r={r} fill="none" stroke="#eef0f6" strokeWidth="16" />
        {total > 0 && segments.map((s) => {
          const len = (s.value / total) * c;
          const el = (
            <circle key={s.label} cx="70" cy="70" r={r} fill="none" stroke={s.color} strokeWidth="16"
              strokeDasharray={`${len} ${c - len}`} strokeDashoffset={-offset} transform="rotate(-90 70 70)" />
          );
          offset += len;
          return el;
        })}
        <text x="70" y="68" textAnchor="middle" className="donut-num">{total}</text>
        <text x="70" y="86" textAnchor="middle" className="donut-lbl">{label}</text>
      </svg>
      <ul className="legend">
        {segments.map((s) => (
          <li key={s.label}><i style={{ background: s.color }} />{s.label}<b>{s.value}</b></li>
        ))}
      </ul>
    </div>
  );
}

export function Bars({ items, empty = "No data yet" }) {
  const max = Math.max(1, ...items.map((i) => i[1]));
  if (!items.length) return <p className="muted">{empty}</p>;
  return (
    <div className="bars">
      {items.map(([k, v]) => (
        <div className="bar-row" key={k}>
          <span>{k}</span>
          <div className="bar-track"><div className="bar-fill" style={{ width: `${(v / max) * 100}%` }} /></div>
          <b>{v}</b>
        </div>
      ))}
    </div>
  );
}

export function Progress({ stage }) {
  const stages = ["Requested", "Provisioning", "Completed"];
  const idx = stage === "Completed" ? 2 : stage === "Provisioning" ? 1 : 0;
  return (
    <div className="progress">
      {stages.map((s, i) => (
        <div key={s} className={i <= idx ? "pstep on" : "pstep"}>
          <span className="pdot" />
          <span>{stage === "Pending Approval" && i === 0 ? "Pending approval" : s}</span>
        </div>
      ))}
    </div>
  );
}

export function Modal({ title, onClose, children }) {
  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose}><Icon name="x" /></button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
