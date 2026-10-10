import re
import uuid

from . import audit, automation, classifier, config, llm, services, software, tickets
from .db import now

LOW_CONF_MSG = ("I couldn't find reliable information about this in the approved IT knowledge base, so I won't "
                "guess. I can raise a ticket so a human helpdesk agent can help you.")


def _user(emp):
    rows = services.store.find("users", {"employee_id": emp})
    return rows[0] if rows else {"employee_id": emp, "name": emp, "email": ""}


def new_analysis(message, employee_id):
    u = _user(employee_id)
    return {"analysis_id": uuid.uuid4().hex[:8], "created_at": now(), "employee_id": employee_id,
            "employee_name": u["name"], "message": message, "intent": None, "intent_confidence": 0.0,
            "intent_reasoning": "", "category": None, "subcategory": None, "priority": None, "impact": None,
            "urgency": None, "assignment_group": None, "summary": None, "suggested_resolution": None,
            "steps": [], "confidence": 0.0, "confidence_threshold": config.CONFIDENCE_THRESHOLD, "sources": [],
            "answer_model": None, "automation": None, "ticket": None, "software_request": None,
            "escalation_recommended": False, "escalated": False, "response": ""}


def _steps(hits):
    for h in hits:
        found = [m.group(1).strip() for m in re.finditer(r"^\s*\d+[.)]\s+(.*)$", h["text"], re.M)]
        if found:
            return found[:6]
    return []


def _fill_from_kb(a, res):
    a["sources"] = res["sources"]
    a["steps"] = _steps(res["hits"])
    a["suggested_resolution"] = res["sources"][0]["title"]


def _knowledge(a, msg, user):
    res = services.kb.search(msg)
    a["confidence"] = res["confidence"]
    if res["confidence"] >= config.CONFIDENCE_THRESHOLD and res["sources"]:
        _fill_from_kb(a, res)
        a["category"] = res["sources"][0]["category"]
        a["response"], a["answer_model"] = llm.generate_answer(msg, res["hits"])
    else:
        a.update(category="Unknown", escalation_recommended=True, response=LOW_CONF_MSG)
        audit.log("rag.low_confidence", "ai-orchestrator", user["employee_id"],
                  f"Confidence {res['confidence']} < threshold {config.CONFIDENCE_THRESHOLD}; answer withheld, escalation offered",
                  status="warn", analysis_id=a["analysis_id"])
        if config.AUTO_ESCALATE:
            escalate_analysis(a)


def _incident(a, msg, user):
    f = classifier.classify_incident(msg)
    res = services.kb.search(msg)
    good = res["confidence"] >= config.CONFIDENCE_THRESHOLD and bool(res["sources"])
    a["confidence"] = round((0.9 if f["matched"] else 0.4) / 2 + res["confidence"] / 2, 2)
    a.update({k: f[k] for k in ("category", "subcategory", "priority", "impact", "urgency", "assignment_group", "summary")})
    if good:
        _fill_from_kb(a, res)
    else:
        a["suggested_resolution"] = f"No approved KB article found - routed to {f['assignment_group']} for triage"
    t = tickets.create(a, f, user, note=f"AI confidence {a['confidence']}; suggested resolution: {a['suggested_resolution']}")
    a["ticket"] = tickets.ref(t)
    txt = (f"I've logged incident {t['number']} ({t['priority']}, {t['category']} / {t['subcategory']}) and assigned it "
           f"to {t['assignment_group']}.")
    if a["steps"]:
        txt += f"\n\nWhile you wait, try this ({a['suggested_resolution']}):\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(a["steps"], 1))
    a["response"] = txt


def _automatable(a, msg, user):
    key = automation.match(msg)
    f = classifier.classify_incident(msg)
    res = services.kb.search(msg)
    out = automation.run(a, msg, user, key, f, res)
    a.update({k: f[k] for k in ("category", "subcategory", "priority", "impact", "urgency", "assignment_group", "summary")})
    a["confidence"] = res["confidence"]
    if res["sources"]:
        _fill_from_kb(a, res)
    a["automation"] = out
    a["ticket"] = out["ticket"]
    if out["status"] == "resolved":
        last = next(s for s in out["steps"] if s["step"] == "Execute")
        a["response"] = (f"Done - {last['detail']}.\n\nI validated the fix and ticket {out['ticket']['number']} has been "
                         "resolved automatically. Every action is recorded in the audit log.")
    else:
        a["response"] = (f"I couldn't safely automate this, so I opened {out['ticket']['number']} for "
                         f"{out['ticket']['assignment_group']}.")


def _service_request(a, msg, user):
    sw = software.find(msg)
    a.update(category="Software", subcategory="Installation", priority="P4", assignment_group="Software Provisioning")
    if not sw:
        names = ", ".join(s["name"] for s in software.CATALOG)
        a.update(escalation_recommended=True, confidence=0.4,
                 response=f"That software isn't in the approved catalogue. Available: {names}. "
                          "I can raise a ticket if you need something else reviewed.")
        return
    rec = software.request(a, user, sw)
    a["confidence"] = 0.95
    a["summary"] = f"Software installation: {sw['name']}"
    a["software_request"] = rec
    a["suggested_resolution"] = "Software Installation"
    a["sources"] = [{"article_id": "software-installation", "title": "Software Installation", "category": "Software",
                     "chunk_id": "software-installation#0", "score": 1.0, "confidence": 0.95}]
    if rec["status"] == "Pending Approval":
        a["response"] = (f"{sw['name']} is licensed software and needs manager approval. Service request "
                         f"{rec['request_id']} was created and is pending approval.")
    else:
        a["response"] = (f"Request {rec['request_id']} created in ServiceNow for {sw['name']}. Status: Provisioning "
                         "(automated install on your laptop in a few minutes).")


ROUTES = {"Knowledge Question": _knowledge, "Incident": _incident, "Automatable Issue": _automatable,
          "Service Request": _service_request}


def handle_message(message, employee_id="emp001"):
    user = _user(employee_id)
    a = new_analysis(message, employee_id)
    a["intent"], a["intent_confidence"], a["intent_reasoning"] = classifier.detect_intent(message)
    audit.log("intent.detected", "ai-orchestrator", employee_id, f"{a['intent']} ({a['intent_confidence']}): {a['intent_reasoning']}",
              analysis_id=a["analysis_id"])
    ROUTES[a["intent"]](a, message, user)
    a["confidence"] = round(a["confidence"], 2)
    services.store.insert("analyses", a)
    services.store.insert("chat_history", {"employee_id": employee_id, "role": "user", "text": message,
                                           "analysis_id": a["analysis_id"], "at": now()})
    services.store.insert("chat_history", {"employee_id": employee_id, "role": "assistant", "text": a["response"],
                                           "analysis_id": a["analysis_id"], "at": now()})
    return a


def escalate_analysis(a):
    if a.get("ticket"):
        return a
    user = _user(a["employee_id"])
    f = classifier.classify_incident(a["message"])
    note = (f"Escalated to human helpdesk. AI confidence {a['confidence']} (threshold {config.CONFIDENCE_THRESHOLD}) "
            "or requested by the employee; no approved KB answer was given.")
    t = tickets.create(a, f, user, note=note, source="escalated")
    a.update({k: f[k] for k in ("category", "subcategory", "priority", "impact", "urgency", "assignment_group", "summary")})
    a["ticket"], a["escalated"], a["escalation_recommended"] = tickets.ref(t), True, False
    a["response"] += f"\n\nI've escalated this: incident {t['number']} was created and assigned to {t['assignment_group']}."
    audit.log("escalation.human", "ai-orchestrator", a["employee_id"], f"Escalated to helpdesk as {t['number']}",
              ticket=t["number"], analysis_id=a["analysis_id"])
    if services.store.find("analyses", {"analysis_id": a["analysis_id"]}):
        services.store.update("analyses", {"analysis_id": a["analysis_id"]}, a)
    return a
