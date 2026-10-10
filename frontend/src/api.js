const BASE = import.meta.env.VITE_API_URL || "";

async function req(path, opts) {
  const r = await fetch(BASE + path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
}

const post = (path, body) => req(path, { method: "POST", body: JSON.stringify(body || {}) });

export const api = {
  employees: () => req("/api/employees"),
  health: () => req("/api/health"),
  chat: (message, employee_id) => post("/api/chat", { message, employee_id }),
  escalate: (analysis_id) => post("/api/tickets/escalate", { analysis_id }),
  dashboard: () => req("/api/dashboard"),
  analyses: () => req("/api/analyses"),
  articles: () => req("/api/knowledge/articles"),
  search: (q) => req("/api/knowledge/search?q=" + encodeURIComponent(q)),
  completeSoftware: (id) => post(`/api/software/requests/${id}/complete`),
  reset: () => post("/api/demo/reset"),
};
