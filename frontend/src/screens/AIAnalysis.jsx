import { useEffect, useState } from "react";
import { api } from "../api";
import { Confidence, Icon, Pill, Steps } from "../components/ui.jsx";

const INTENT_TONE = { Incident: "danger", "Knowledge Question": "primary", "Automatable Issue": "success", "Service Request": "info" };

function Tile({ label, children }) {
  return (
    <div className="tile">
      <span>{label}</span>
      <b>{children || "-"}</b>
    </div>
  );
}

export default function AIAnalysis({ latest }) {
  const [list, setList] = useState([]);
  const [sel, setSel] = useState(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    api.analyses().then((l) => {
      setList(l);
      setSel((s) => latest?.analysis_id || s || l[0]?.analysis_id);
    });
  }, [latest]);

  const shown = list.filter((x) => x.message.toLowerCase().includes(filter.toLowerCase()));
  const a = list.find((x) => x.analysis_id === sel);

  return (
    <div className="split">
      <div className="card list-card">
        <div className="search-box">
          <Icon name="search" size={16} />
          <input value={filter} placeholder="Filter conversations" onChange={(e) => setFilter(e.target.value)} />
        </div>
        <div className="list">
          {shown.length === 0 && <p className="muted pad">No analyses yet. Ask something in Self-Service.</p>}
          {shown.map((x) => (
            <button key={x.analysis_id} className={x.analysis_id === sel ? "list-item active" : "list-item"} onClick={() => setSel(x.analysis_id)}>
              <Pill tone={INTENT_TONE[x.intent] || "neutral"}>{x.intent}</Pill>
              <span className="li-text">{x.message}</span>
              <span className="li-meta">{x.analysis_id} · {x.employee_name}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="stack">
        {!a ? (
          <div className="card empty-state">Select a conversation to inspect the AI decision.</div>
        ) : (
          <>
            <div className="card hero">
              <div className="mini-title"><Icon name="chat" size={14} />Employee request · {a.employee_name}</div>
              <p className="quote">{a.message}</p>
              <p className="muted">{a.intent_reasoning}</p>
            </div>

            <div className="tiles">
              <Tile label="Intent"><Pill tone={INTENT_TONE[a.intent] || "neutral"}>{a.intent}</Pill></Tile>
              <Tile label="Category">{a.category && `${a.category}${a.subcategory ? " / " + a.subcategory : ""}`}</Tile>
              <Tile label="Priority">{a.priority && <Pill tone={a.priority === "P1" ? "danger" : a.priority === "P2" ? "warn" : "neutral"}>{a.priority}</Pill>}</Tile>
              <Tile label="Impact / Urgency">{a.impact && `${a.impact} / ${a.urgency}`}</Tile>
              <Tile label="Assignment group">{a.assignment_group}</Tile>
              <Tile label="Summary">{a.summary}</Tile>
            </div>

            <div className="grid2">
              <div className="card">
                <h3>Confidence and governance</h3>
                <Confidence value={a.confidence} threshold={a.confidence_threshold} />
                <p className="muted">
                  Intent confidence {Math.round(a.intent_confidence * 100)}%
                  {a.escalated ? " · escalated to a human agent" : a.escalation_recommended ? " · escalation offered to the employee" : ""}
                </p>
                <p className="muted">Answer model: <b>{a.answer_model || "not used"}</b></p>
              </div>
              <div className="card">
                <h3>ServiceNow reference</h3>
                {a.ticket ? (
                  <div className="ref-card">
                    <Icon name="ticket" />
                    <div>
                      <div className="ref-id">{a.ticket.number}</div>
                      <div className="muted">{a.ticket.priority} · {a.ticket.assignment_group} · {a.ticket.mode}</div>
                    </div>
                    <Pill tone={a.ticket.state === "Resolved" ? "success" : "info"}>{a.ticket.state}</Pill>
                  </div>
                ) : a.software_request ? (
                  <div className="ref-card">
                    <Icon name="package" />
                    <div>
                      <div className="ref-id">{a.software_request.request_id}</div>
                      <div className="muted">{a.software_request.software}</div>
                    </div>
                    <Pill tone="info">{a.software_request.status}</Pill>
                  </div>
                ) : (
                  <p className="muted">No ServiceNow record for this conversation.</p>
                )}
                <h4>Suggested resolution</h4>
                <p>{a.suggested_resolution || "-"}</p>
              </div>
            </div>

            <div className="card">
              <h3>Knowledge sources used</h3>
              {a.sources.length === 0 ? (
                <p className="muted">None. The approved knowledge base did not contain enough information, so no answer was generated.</p>
              ) : (
                <div className="source-list">
                  {a.sources.map((s) => (
                    <div className="source-row" key={s.chunk_id}>
                      <Icon name="file" />
                      <div>
                        <b>{s.title}</b>
                        <div className="muted">{s.category} · chunk {s.chunk_id} · similarity {s.score}</div>
                      </div>
                      <Pill tone={s.confidence >= a.confidence_threshold ? "success" : "warn"}>{Math.round(s.confidence * 100)}%</Pill>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {a.automation && (
              <div className="card">
                <h3>Automation · {a.automation.label} <Pill tone={a.automation.status === "resolved" ? "success" : "warn"}>{a.automation.status}</Pill></h3>
                <Steps steps={a.automation.steps} />
              </div>
            )}

            {a.steps.length > 0 && (
              <div className="card">
                <h3>Suggested steps</h3>
                <ol className="num-list">{a.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
              </div>
            )}

            <div className="card">
              <h3>Response sent to the employee</h3>
              <pre>{a.response}</pre>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
