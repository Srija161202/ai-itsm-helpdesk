import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Confidence, Icon, Pill, Progress, Steps } from "../components/ui.jsx";

const SCENARIOS = [
  { icon: "alert", title: "Report an incident", text: "My VPN is not connecting." },
  { icon: "bolt", title: "Self-heal an issue", text: "My password has expired." },
  { icon: "book", title: "Ask a question", text: "How do I troubleshoot Outlook synchronization?" },
  { icon: "package", title: "Request software", text: "I need Visual Studio Code." },
  { icon: "shield", title: "Unsupported question", text: "What is the company policy on parental leave?" },
];

const INTENT_TONE = { Incident: "danger", "Knowledge Question": "primary", "Automatable Issue": "success", "Service Request": "info" };
const STATE_TONE = { New: "info", "In Progress": "warn", Resolved: "success", Closed: "neutral" };

function Answer({ m, onTicket, openAnalysis }) {
  const a = m.analysis;
  return (
    <div className="msg assistant">
      <span className="bot"><Icon name="spark" size={16} /></span>
      <div className="bubble">
        <div className="text">{m.text}</div>
        {a && (
          <div className="insight">
            <div className="pill-row">
              <Pill tone={INTENT_TONE[a.intent] || "neutral"}>{a.intent}</Pill>
              {a.category && <Pill>{a.category}{a.subcategory ? ` / ${a.subcategory}` : ""}</Pill>}
              {a.priority && <Pill tone={a.priority === "P1" ? "danger" : a.priority === "P2" ? "warn" : "neutral"}>{a.priority}</Pill>}
              {a.assignment_group && <Pill>{a.assignment_group}</Pill>}
            </div>
            <Confidence value={a.confidence} threshold={a.confidence_threshold} compact />
            {a.automation && <Steps steps={a.automation.steps} />}
            {a.steps.length > 0 && !a.automation && (
              <div className="resolution">
                <div className="mini-title"><Icon name="list" size={14} />Suggested resolution · {a.suggested_resolution}</div>
                <ol>{a.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
              </div>
            )}
            {a.ticket && (
              <div className="ref-card">
                <Icon name="ticket" />
                <div>
                  <div className="ref-id">{a.ticket.number}</div>
                  <div className="muted">{a.ticket.assignment_group} · {a.ticket.mode} ServiceNow</div>
                </div>
                <Pill tone={STATE_TONE[a.ticket.state] || "neutral"}>{a.ticket.state}</Pill>
              </div>
            )}
            {a.software_request && (
              <div className="ref-card col">
                <div className="ref-row">
                  <Icon name="package" />
                  <div>
                    <div className="ref-id">{a.software_request.request_id}</div>
                    <div className="muted">{a.software_request.software}</div>
                  </div>
                  <Pill tone="info">{a.software_request.status}</Pill>
                </div>
                <Progress stage={a.software_request.status} />
                <div className="success-note"><Icon name="check" size={14} />ServiceNow request created successfully</div>
              </div>
            )}
            {a.sources.length > 0 && (
              <div className="sources">
                <span className="mini-title"><Icon name="file" size={14} />Sources</span>
                {a.sources.map((s) => (
                  <span key={s.chunk_id} className="source">{s.title}<b>{Math.round(s.confidence * 100)}%</b></span>
                ))}
              </div>
            )}
            <div className="actions">
              {!a.ticket && !a.software_request && (
                <button className={a.escalation_recommended ? "btn danger" : "btn soft"} onClick={() => onTicket(a)}>
                  <Icon name="ticket" size={15} />
                  {a.escalation_recommended ? "Escalate to helpdesk" : "Create ticket anyway"}
                </button>
              )}
              <button className="btn ghost" onClick={openAnalysis}><Icon name="brain" size={15} />View AI analysis</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function SelfService({ employeeId, onAnalysis, openAnalysis }) {
  const [messages, setMessages] = useState([
    { role: "assistant", text: "Hi! I can answer IT questions from approved knowledge, log incidents, fix common problems automatically and request software for you. What do you need today?" },
  ]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  async function send(t) {
    const msg = (t ?? text).trim();
    if (!msg || busy) return;
    setText("");
    setMessages((m) => [...m, { role: "user", text: msg }]);
    setBusy(true);
    try {
      const a = await api.chat(msg, employeeId);
      setMessages((m) => [...m, { role: "assistant", text: a.response, analysis: a }]);
      onAnalysis(a);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", text: "Sorry, something went wrong: " + e.message }]);
    } finally {
      setBusy(false);
    }
  }

  async function createTicket(a) {
    try {
      const r = await api.escalate(a.analysis_id);
      setMessages((m) => m.map((x) => (x.analysis?.analysis_id === a.analysis_id ? { ...x, text: r.response, analysis: r } : x)));
      onAnalysis(r);
    } catch (e) {
      setMessages((m) => [...m, { role: "assistant", text: "Could not create the ticket: " + e.message }]);
    }
  }

  return (
    <div className="chat-layout">
      <section className="card chat">
        <div className="chat-top">
          <span className="bot big"><Icon name="spark" size={18} /></span>
          <div>
            <div className="chat-name">IT Assistant</div>
            <div className="online"><i />Online · grounded in approved knowledge</div>
          </div>
        </div>
        <div className="log">
          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="msg user"><div className="bubble">{m.text}</div></div>
            ) : (
              <Answer key={i} m={m} onTicket={createTicket} openAnalysis={openAnalysis} />
            )
          )}
          {busy && (
            <div className="msg assistant">
              <span className="bot"><Icon name="spark" size={16} /></span>
              <div className="bubble typing"><i /><i /><i /></div>
            </div>
          )}
          <div ref={end} />
        </div>
        <div className="composer">
          <input value={text} placeholder="Describe your issue, ask a question or request software..."
            onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()} />
          <button className="btn primary" disabled={busy || !text.trim()} onClick={() => send()}>
            <Icon name="send" size={16} />Send
          </button>
        </div>
      </section>
      <aside className="side">
        <div className="card">
          <h3>Try a scenario</h3>
          <p className="muted">One click runs each required demo flow.</p>
          <div className="scenarios">
            {SCENARIOS.map((s) => (
              <button key={s.text} className="scenario" disabled={busy} onClick={() => send(s.text)}>
                <span className="s-icon"><Icon name={s.icon} size={16} /></span>
                <span>
                  <b>{s.title}</b>
                  <em>{s.text}</em>
                </span>
              </button>
            ))}
          </div>
        </div>
        <div className="card tip">
          <h3>How it works</h3>
          <ol className="flow">
            <li>AI detects the intent</li>
            <li>Searches approved knowledge</li>
            <li>Acts safely or opens a ticket</li>
            <li>Escalates when unsure</li>
          </ol>
        </div>
      </aside>
    </div>
  );
}
