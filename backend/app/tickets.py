from . import audit, servicenow, services
from .db import now


def ref(t):
    return {"number": t["number"], "sys_id": t["sys_id"], "state": t["state"], "priority": t["priority"],
            "assignment_group": t["assignment_group"], "mode": t["servicenow_mode"]}


def create(a, fields, user, note="", source="ai_incident"):
    payload = servicenow.build_incident_payload(fields, a["message"], user, note)
    inc = services.sn.create_incident(payload)
    t = {"number": inc["number"], "sys_id": inc["sys_id"], "source": source, "state": inc["state"],
         "short_description": inc["short_description"], "category": inc["category"],
         "subcategory": inc["subcategory"], "priority": inc["priority"], "impact": inc["impact"],
         "urgency": inc["urgency"], "assignment_group": inc["assignment_group"],
         "employee_id": user["employee_id"], "analysis_id": a["analysis_id"], "ai_resolved": False,
         "escalated": source == "escalated", "created_at": now(), "updated_at": now(),
         "servicenow_mode": inc["mode"]}
    services.store.insert("tickets", t)
    audit.log("servicenow.create_incident", "ai-orchestrator", user["employee_id"],
              f"Created {t['number']} [{t['category']}/{t['subcategory']}, {t['priority']}] -> {t['assignment_group']}",
              ticket=t["number"], analysis_id=a["analysis_id"])
    return t


def resolve(number, notes, by_ai=True):
    services.sn.update_incident(number, {"state": "Resolved", "close_notes": notes, "work_notes": notes})
    services.store.update("tickets", {"number": number}, {"state": "Resolved", "ai_resolved": by_ai, "updated_at": now()})
