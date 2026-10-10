import uuid
from . import services
from .db import now


def log(action, actor, employee_id, detail, status="success", ticket=None, analysis_id=None, meta=None):
    rec = {"audit_id": uuid.uuid4().hex[:10], "timestamp": now(), "action": action, "actor": actor,
           "employee_id": employee_id, "status": status, "detail": detail, "ticket": ticket,
           "analysis_id": analysis_id, "meta": meta or {}}
    services.store.insert("audit_logs", rec)
    return rec
