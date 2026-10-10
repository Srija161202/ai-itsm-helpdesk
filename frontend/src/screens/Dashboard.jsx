import { useEffect, useState } from "react";
import { api } from "../api";
import { Bars, Donut, Icon, Pill, Progress } from "../components/ui.jsx";

const KPIS = [
  ["total_tickets", "Total tickets", "ticket", "indigo"],
  ["open_tickets", "Open tickets", "alert", "amber"],
  ["ai_resolved", "AI-resolved", "bolt", "green"],
  ["escalated", "Escalated", "shield", "red"],
  ["software_requests", "Software requests", "package", "blue"],
  ["conversations", "Conversations", "chat", "violet"],
];

const STATE_TONE = { New: "info", "In Progress": "warn", Resolved: "success", Closed: "neutral" };
const SW_TONE = { Provisioning: "info", Completed: "success", "Pending Approval": "warn" };
const AUDIT_TONE = { success: "success", failed: "danger", warn: "warn" };

export default function Dashboard() {
  const [d, setD] = useState(null);
  const load = () => api.dashboard().then(setD).catch(() => {});

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  if (!d) return <div className="card">Loading dashboard...</div>;

  const k = d.kpis;
  const other = Math.max(0, k.total_tickets - k.ai_resolved - k.escalated);
  const swTotal = d.software.provisioning + d.software.completed + d.software.pending_approval;

  return (
    <div className="stack">
      <div className="toolbar">
        <span className="live"><i />Live · refreshes every 4s</span>
        <button className="btn ghost" onClick={() => api.reset().then(load)}><Icon name="refresh" size={15} />Reset demo data</button>
      </div>

      <div className="kpis">
        {KPIS.map(([key, label, icon, tone]) => (
          <div className="kpi card" key={key}>
            <span className={`kpi-icon ${tone}`}><Icon name={icon} /></span>
            <div className="kpi-num">{k[key]}</div>
            <div className="kpi-label">{label}</div>
          </div>
        ))}
      </div>

      <div className="grid3">
        <div className="card">
          <h3>Ticket outcomes</h3>
          <Donut label="tickets" segments={[
            { label: "AI-resolved", value: k.ai_resolved, color: "#12b76a" },
            { label: "Escalated", value: k.escalated, color: "#f04438" },
            { label: "AI-triaged", value: other, color: "#6366f1" },
          ]} />
        </div>
        <div className="card">
          <h3>Automation status</h3>
          <div className="duo">
            <div><b>{d.automation.executed}</b><span>executed</span></div>
            <div><b>{d.automation.succeeded}</b><span>succeeded</span></div>
          </div>
          <Bars items={Object.entries(d.automation.by_action)} empty="No automated actions yet" />
        </div>
        <div className="card">
          <h3>Software provisioning</h3>
          <div className="duo three">
            <div><b>{d.software.provisioning}</b><span>provisioning</span></div>
            <div><b>{d.software.completed}</b><span>completed</span></div>
            <div><b>{d.software.pending_approval}</b><span>approval</span></div>
          </div>
          <div className="meter"><div style={{ width: `${swTotal ? (d.software.completed / swTotal) * 100 : 0}%` }} /></div>
          <p className="muted">{swTotal ? `${d.software.completed} of ${swTotal} requests completed` : "No software requests yet"}</p>
        </div>
      </div>

      <div className="card">
        <h3>Software requests</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Request</th><th>Software</th><th>Employee</th><th>Pipeline</th><th>Status</th><th /></tr></thead>
            <tbody>
              {d.software_requests.length === 0 && <tr><td colSpan="6" className="empty">No requests yet</td></tr>}
              {d.software_requests.map((r) => (
                <tr key={r.request_id}>
                  <td className="mono">{r.request_id}</td>
                  <td>{r.software}</td>
                  <td>{r.employee_id}</td>
                  <td className="wide"><Progress stage={r.status} /></td>
                  <td><Pill tone={SW_TONE[r.status] || "neutral"}>{r.status}</Pill></td>
                  <td>{r.status === "Provisioning" && <button className="btn tiny" onClick={() => api.completeSoftware(r.request_id).then(load)}>Complete</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3>Recent ServiceNow tickets</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Number</th><th>Summary</th><th>Category</th><th>Priority</th><th>Group</th><th>State</th><th>Handled by</th></tr></thead>
            <tbody>
              {d.recent_tickets.length === 0 && <tr><td colSpan="7" className="empty">No tickets yet</td></tr>}
              {d.recent_tickets.map((t) => (
                <tr key={t.number}>
                  <td className="mono">{t.number}</td>
                  <td>{t.short_description}</td>
                  <td>{t.category} / {t.subcategory}</td>
                  <td><Pill tone={t.priority === "P1" ? "danger" : t.priority === "P2" ? "warn" : "neutral"}>{t.priority}</Pill></td>
                  <td>{t.assignment_group}</td>
                  <td><Pill tone={STATE_TONE[t.state] || "neutral"}>{t.state}</Pill></td>
                  <td>{t.escalated ? <Pill tone="danger">Escalated</Pill> : t.ai_resolved ? <Pill tone="success">AI-resolved</Pill> : <Pill tone="primary">AI-triaged</Pill>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3>Audit log</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Detail</th><th>Ticket</th><th>Status</th></tr></thead>
            <tbody>
              {d.recent_audit.length === 0 && <tr><td colSpan="6" className="empty">No audit entries yet</td></tr>}
              {d.recent_audit.map((l) => (
                <tr key={l.audit_id}>
                  <td className="mono">{l.timestamp.slice(11, 19)}</td>
                  <td>{l.actor}</td>
                  <td className="mono">{l.action}</td>
                  <td>{l.detail}</td>
                  <td className="mono">{l.ticket}</td>
                  <td><Pill tone={AUDIT_TONE[l.status] || "neutral"}>{l.status}</Pill></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
