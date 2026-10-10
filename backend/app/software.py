import re
import time
import uuid

from . import audit, config, services
from .db import now

CATALOG = [
    {"id": "vscode", "name": "Visual Studio Code", "aliases": ["visual studio code", "vs code", "vscode"], "category": "Developer Tools", "approval_required": False},
    {"id": "git", "name": "Git", "aliases": ["git"], "category": "Developer Tools", "approval_required": False},
    {"id": "python", "name": "Python 3", "aliases": ["python"], "category": "Developer Tools", "approval_required": False},
    {"id": "chrome", "name": "Google Chrome", "aliases": ["google chrome", "chrome"], "category": "Browsers", "approval_required": False},
    {"id": "firefox", "name": "Mozilla Firefox", "aliases": ["firefox"], "category": "Browsers", "approval_required": False},
    {"id": "zoom", "name": "Zoom", "aliases": ["zoom"], "category": "Collaboration", "approval_required": False},
    {"id": "slack", "name": "Slack", "aliases": ["slack"], "category": "Collaboration", "approval_required": False},
    {"id": "7zip", "name": "7-Zip", "aliases": ["7-zip", "7zip"], "category": "Utilities", "approval_required": False},
    {"id": "visio", "name": "Microsoft Visio", "aliases": ["visio"], "category": "Licensed Software", "approval_required": True},
    {"id": "acrobat", "name": "Adobe Acrobat Pro", "aliases": ["acrobat pro", "adobe acrobat", "acrobat"], "category": "Licensed Software", "approval_required": True},
]


def find(text):
    t = text.lower()
    best = None
    for sw in CATALOG:
        for alias in sw["aliases"]:
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", t):
                if best is None or len(alias) > best[0]:
                    best = (len(alias), sw)
    return best[1] if best else None


def mock_provisioning_api(sw, user):
    return {"job_id": f"PRV-{uuid.uuid4().hex[:6].upper()}", "status": "Provisioning",
            "target": f"{user['employee_id']}-laptop", "package": sw["id"]}


def request(a, user, sw):
    sn_req = services.sn.create_request({
        "short_description": f"Software installation: {sw['name']}",
        "description": f"{user['name']} requested {sw['name']} via AI self-service. Original message: {a['message']}",
        "requested_for": user.get("email", ""), "catalog_item": sw["name"]})
    job, status = None, "Pending Approval"
    if not sw["approval_required"]:
        job = mock_provisioning_api(sw, user)
        status = "Provisioning"
        audit.log("software.provision_started", "provisioning-agent", user["employee_id"],
                  f"Mock provisioning job {job['job_id']} started for {sw['name']} on {job['target']}",
                  ticket=sn_req["number"], analysis_id=a["analysis_id"], meta={"software": sw["id"]})
    rec = {"request_id": sn_req["number"], "sys_id": sn_req["sys_id"], "software_id": sw["id"],
           "software": sw["name"], "employee_id": user["employee_id"], "status": status,
           "job_id": job["job_id"] if job else None, "approval_required": sw["approval_required"],
           "analysis_id": a["analysis_id"], "created_at": now(), "created_ts": time.time(), "updated_at": now(),
           "servicenow_mode": sn_req["mode"]}
    services.store.insert("software_requests", rec)
    audit.log("servicenow.create_request", "ai-orchestrator", user["employee_id"],
              f"Created service request {rec['request_id']} for {sw['name']} (status: {status})",
              ticket=rec["request_id"], analysis_id=a["analysis_id"])
    return rec


def complete(request_id):
    rows = services.store.find("software_requests", {"request_id": request_id})
    if not rows:
        return None
    rec = rows[0]
    if rec["status"] == "Provisioning":
        services.store.update("software_requests", {"request_id": request_id}, {"status": "Completed", "updated_at": now()})
        services.sn.update_request(request_id, {"state": "Closed Complete", "work_notes": "Provisioning completed (mock)"})
        audit.log("software.provision_completed", "provisioning-agent", rec["employee_id"],
                  f"{rec['software']} installed (mock) - job {rec['job_id']}", ticket=request_id)
        rec["status"] = "Completed"
    return rec


def refresh(rec):
    if rec["status"] == "Provisioning" and time.time() - rec.get("created_ts", 0) >= config.PROVISION_SECONDS:
        return complete(rec["request_id"]) or rec
    return rec
