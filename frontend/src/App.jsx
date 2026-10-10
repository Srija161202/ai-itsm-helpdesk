import { useEffect, useState } from "react";
import { api } from "./api";
import { Avatar, Icon, Pill } from "./components/ui.jsx";
import SelfService from "./screens/SelfService.jsx";
import Dashboard from "./screens/Dashboard.jsx";
import AIAnalysis from "./screens/AIAnalysis.jsx";
import KnowledgeBase from "./screens/KnowledgeBase.jsx";

const TABS = [
  { id: "self", label: "Self-Service", icon: "chat", title: "Employee Self-Service", sub: "Ask, report or request - the AI routes it for you" },
  { id: "dash", label: "ITSM Dashboard", icon: "dashboard", title: "ITSM Dashboard", sub: "Tickets, automation and software provisioning at a glance" },
  { id: "ai", label: "AI Analysis", icon: "brain", title: "AI Analysis", sub: "How the AI understood, decided and acted on each request" },
  { id: "kb", label: "Knowledge Base", icon: "book", title: "Knowledge Base", sub: "Approved articles and RAG search results" },
];

export default function App() {
  const [tab, setTab] = useState("self");
  const [employees, setEmployees] = useState([]);
  const [employeeId, setEmployeeId] = useState("emp001");
  const [health, setHealth] = useState(null);
  const [offline, setOffline] = useState(false);
  const [latest, setLatest] = useState(null);

  useEffect(() => {
    api.employees().then(setEmployees).catch(() => setOffline(true));
    api.health().then(setHealth).catch(() => setOffline(true));
  }, []);

  const current = TABS.find((t) => t.id === tab);
  const user = employees.find((u) => u.employee_id === employeeId);
  const kbName = health ? health.knowledge_base.embedding_model.split("/").pop() : "";

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="logo">
          <span className="logo-mark"><Icon name="spark" size={18} /></span>
          <div>
            <div className="logo-name">HelpDesk AI</div>
            <div className="logo-sub">Intelligent ITSM</div>
          </div>
        </div>
        <nav className="nav">
          {TABS.map((t) => (
            <button key={t.id} className={t.id === tab ? "nav-item active" : "nav-item"} onClick={() => setTab(t.id)}>
              <Icon name={t.icon} />
              {t.label}
            </button>
          ))}
        </nav>
        <div className="sys-card">
          <div className="sys-title">System status</div>
          {offline && <Pill tone="danger" icon="alert">Backend offline</Pill>}
          {health && (
            <ul>
              <li><Icon name="db" size={14} /><span>Database</span><Pill tone="primary">{health.database}</Pill></li>
              <li><Icon name="ticket" size={14} /><span>ServiceNow</span><Pill tone={health.servicenow === "live" ? "success" : "warn"}>{health.servicenow}</Pill></li>
              <li><Icon name="file" size={14} /><span>Vector DB</span><Pill tone="primary">{health.knowledge_base.vector_db}</Pill></li>
              <li><Icon name="brain" size={14} /><span>LLM</span><Pill tone="neutral">{health.llm.split("/").pop()}</Pill></li>
              <li><Icon name="search" size={14} /><span>Embeddings</span><Pill tone="neutral">{kbName}</Pill></li>
            </ul>
          )}
        </div>
      </aside>
      <div className="content">
        <header className="header">
          <div>
            <h1>{current.title}</h1>
            <p>{current.sub}</p>
          </div>
          <label className="who">
            <Avatar name={user ? user.name : "Employee"} />
            <select value={employeeId} onChange={(e) => setEmployeeId(e.target.value)}>
              {employees.map((u) => (
                <option key={u.employee_id} value={u.employee_id}>{u.name} · {u.department}</option>
              ))}
            </select>
          </label>
        </header>
        <main className="page">
          {tab === "self" && <SelfService employeeId={employeeId} onAnalysis={setLatest} openAnalysis={() => setTab("ai")} />}
          {tab === "dash" && <Dashboard />}
          {tab === "ai" && <AIAnalysis latest={latest} />}
          {tab === "kb" && <KnowledgeBase />}
        </main>
      </div>
    </div>
  );
}
