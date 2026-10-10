import logging
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import config, llm, orchestrator, services, software, tickets
from .db import now

logging.basicConfig(level=logging.INFO)
OPEN_STATES = {"New", "In Progress", "On Hold"}


@asynccontextmanager
async def lifespan(app):
    services.init()
    if config.USE_LLM:
        threading.Thread(target=llm.warmup, daemon=True).start()
    yield


app = FastAPI(title="AI ITSM & Helpdesk Automation Platform", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ChatIn(BaseModel):
    message: str
    employee_id: str = "emp001"


class EscalateIn(BaseModel):
    analysis_id: Optional[str] = None
    message: Optional[str] = None
    employee_id: str = "emp001"


class TicketPatch(BaseModel):
    state: Optional[str] = None
    work_notes: Optional[str] = None


class SoftwareIn(BaseModel):
    software_id: str
    employee_id: str = "emp001"


@app.get("/api/health")
def health():
    return {"status": "ok", "database": services.store.backend, "servicenow": services.sn.mode,
            "llm": config.LLM_MODEL if config.USE_LLM else "extractive-only", "knowledge_base": services.kb.info(),
            "confidence_threshold": config.CONFIDENCE_THRESHOLD}


@app.get("/api/employees")
def employees():
    return services.store.find("users")


@app.post("/api/chat")
def chat(body: ChatIn):
    if not body.message.strip():
        raise HTTPException(400, "message is empty")
    return orchestrator.handle_message(body.message.strip(), body.employee_id)


@app.get("/api/chat/history")
def chat_history(employee_id: str = "emp001"):
    return services.store.find("chat_history", {"employee_id": employee_id}, sort=("at", 1))


@app.post("/api/tickets/escalate")
def escalate(body: EscalateIn):
    if body.analysis_id:
        rows = services.store.find("analyses", {"analysis_id": body.analysis_id})
        if not rows:
            raise HTTPException(404, "analysis not found")
        a = rows[0]
    elif body.message:
        a = orchestrator.new_analysis(body.message, body.employee_id)
        a["intent"] = "Incident"
    else:
        raise HTTPException(400, "analysis_id or message required")
    return orchestrator.escalate_analysis(a)


@app.get("/api/tickets")
def list_tickets():
    return services.store.find("tickets", sort=("created_at", -1))


@app.get("/api/tickets/{number}")
def get_ticket(number: str):
    inc = services.sn.get_incident(number)
    if not inc:
        raise HTTPException(404, "incident not found")
    local = services.store.find("tickets", {"number": number})
    return {"servicenow": inc, "local": local[0] if local else None}


@app.patch("/api/tickets/{number}")
def patch_ticket(number: str, body: TicketPatch):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    inc = services.sn.update_incident(number, fields)
    if not inc:
        raise HTTPException(404, "incident not found")
    if "state" in fields:
        services.store.update("tickets", {"number": number}, {"state": fields["state"], "updated_at": now()})
    return inc


@app.get("/api/analyses")
def analyses():
    return services.store.find("analyses", sort=("created_at", -1))


@app.get("/api/analyses/{analysis_id}")
def analysis(analysis_id: str):
    rows = services.store.find("analyses", {"analysis_id": analysis_id})
    if not rows:
        raise HTTPException(404, "analysis not found")
    return rows[0]


@app.get("/api/knowledge/articles")
def articles():
    return [{k: a[k] for k in ("article_id", "title", "category", "content")} for a in services.kb.articles]


@app.get("/api/knowledge/search")
def kb_search(q: str = Query(..., min_length=2)):
    res = services.kb.search(q)
    grounded = res["confidence"] >= config.CONFIDENCE_THRESHOLD and bool(res["sources"])
    answer, model = (llm.generate_answer(q, res["hits"]) if grounded else
                     ("Information not available in the approved knowledge base.", None))
    return {**res, "grounded": grounded, "answer": answer, "answer_model": model,
            "threshold": config.CONFIDENCE_THRESHOLD, **services.kb.info()}


@app.get("/api/software/catalog")
def catalog():
    return software.CATALOG


@app.get("/api/software/requests")
def software_requests():
    rows = [software.refresh(r) for r in services.store.find("software_requests", sort=("created_at", -1))]
    return rows


@app.post("/api/software/requests/{request_id}/complete")
def force_complete(request_id: str):
    rec = software.complete(request_id)
    if not rec:
        raise HTTPException(404, "request not found")
    return rec


@app.get("/api/audit")
def audit_log(limit: int = 100):
    return services.store.find("audit_logs", sort=("timestamp", -1), limit=limit)


@app.get("/api/dashboard")
def dashboard():
    t = services.store.find("tickets", sort=("created_at", -1))
    reqs = [software.refresh(r) for r in services.store.find("software_requests", sort=("created_at", -1))]
    logs = services.store.find("audit_logs", sort=("timestamp", -1))
    execs = [l for l in logs if l["action"] == "self_heal.execute"]
    by_action = {}
    for l in execs:
        k = l["meta"].get("automation", "?")
        by_action[k] = by_action.get(k, 0) + 1
    return {
        "kpis": {"total_tickets": len(t), "open_tickets": sum(1 for x in t if x["state"] in OPEN_STATES),
                 "ai_resolved": sum(1 for x in t if x.get("ai_resolved")),
                 "escalated": sum(1 for x in t if x.get("escalated")), "software_requests": len(reqs),
                 "conversations": services.store.count("analyses")},
        "software": {"provisioning": sum(1 for r in reqs if r["status"] == "Provisioning"),
                     "completed": sum(1 for r in reqs if r["status"] == "Completed"),
                     "pending_approval": sum(1 for r in reqs if r["status"] == "Pending Approval")},
        "automation": {"executed": len(execs), "succeeded": sum(1 for l in execs if l["status"] == "success"),
                       "by_action": by_action},
        "recent_tickets": t[:8], "software_requests": reqs[:8], "recent_audit": logs[:12],
        "system": health(),
    }


@app.post("/api/demo/reset")
def demo_reset():
    services.reset_demo()
    return {"status": "reset"}
