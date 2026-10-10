import logging
import uuid

import requests

from . import config
from .db import now

log = logging.getLogger("itsm.sn")

IMPACT = {"Enterprise": "1", "Department": "2", "Individual": "3"}
URGENCY = {"High": "1", "Medium": "2", "Low": "3"}
STATE_NUM = {"New": "1", "In Progress": "2", "On Hold": "3", "Resolved": "6", "Closed": "7"}
STATE_NAME = {v: k for k, v in STATE_NUM.items()}


def build_incident_payload(fields, message, user, note=""):
    desc = (f"Reported by {user['name']} ({user.get('email', '')}) via the AI self-service portal.\n\n"
            f"Employee message: {message}")
    if note:
        desc += f"\n\nAI note: {note}"
    return {"short_description": fields["summary"], "description": desc, "category": fields["category"],
            "subcategory": fields["subcategory"], "impact": fields["impact"], "urgency": fields["urgency"],
            "priority": fields["priority"], "assignment_group": fields["assignment_group"],
            "caller": user.get("email") or user["name"]}


class ServiceNowClient:
    def __init__(self, store):
        self.store = store
        self.live = bool(config.SN_INSTANCE and config.SN_USER and config.SN_PASSWORD)

    @property
    def mode(self):
        return "live" if self.live else "mock"

    def _call(self, method, path, **kw):
        url = f"https://{config.SN_INSTANCE}.service-now.com/api/now/table{path}"
        r = requests.request(method, url, auth=(config.SN_USER, config.SN_PASSWORD),
                             headers={"Accept": "application/json"}, timeout=20, **kw)
        r.raise_for_status()
        return r.json()["result"]

    def _ref(self, table, query):
        rows = self._call("GET", f"/{table}", params={"sysparm_query": query, "sysparm_limit": 1,
                                                      "sysparm_fields": "sys_id"})
        return rows[0]["sys_id"] if rows else ""

    def _live_incident_body(self, p):
        return {"short_description": p["short_description"], "description": p["description"],
                "category": p["category"].lower(), "subcategory": p["subcategory"].lower(),
                "impact": IMPACT[p["impact"]], "urgency": URGENCY[p["urgency"]],
                "assignment_group": self._ref("sys_user_group", f"name={p['assignment_group']}"),
                "caller_id": self._ref("sys_user", f"email={p['caller']}"), "contact_type": "self-service"}

    def create_incident(self, p):
        if self.live:
            try:
                r = self._call("POST", "/incident", json=self._live_incident_body(p))
                return {**p, "number": r["number"], "sys_id": r["sys_id"], "state": "New", "mode": "live"}
            except Exception as exc:
                log.warning("ServiceNow live create failed (%s) - using mock", exc)
        n = self.store.count("sn_incidents")
        rec = {**p, "number": f"INC{10001 + n:07d}", "sys_id": uuid.uuid4().hex, "state": "New",
               "work_notes": [], "close_notes": "", "opened_at": now(), "updated_at": now(), "mode": "mock"}
        self.store.insert("sn_incidents", rec)
        return rec

    def get_incident(self, number):
        if self.live:
            try:
                rows = self._call("GET", "/incident", params={"sysparm_query": f"number={number}", "sysparm_limit": 1})
                if rows:
                    r = rows[0]
                    return {"number": r["number"], "sys_id": r["sys_id"], "state": STATE_NAME.get(r["state"], r["state"]),
                            "short_description": r["short_description"], "description": r.get("description", ""),
                            "category": r.get("category"), "subcategory": r.get("subcategory"),
                            "priority": r.get("priority"), "impact": r.get("impact"), "urgency": r.get("urgency"),
                            "close_notes": r.get("close_notes", ""), "mode": "live"}
            except Exception as exc:
                log.warning("ServiceNow live get failed (%s)", exc)
        rows = self.store.find("sn_incidents", {"number": number})
        return rows[0] if rows else None

    def update_incident(self, number, fields):
        if self.live:
            try:
                rec = self.get_incident(number)
                body = {k: v for k, v in fields.items() if k not in ("state", "close_notes")}
                if "state" in fields:
                    body["state"] = STATE_NUM[fields["state"]]
                    if fields["state"] == "Resolved":
                        body.update({"close_code": "Solved (Permanently)", "close_notes": fields.get("close_notes", "Resolved by AI")})
                self._call("PATCH", f"/incident/{rec['sys_id']}", json=body)
                return self.get_incident(number)
            except Exception as exc:
                log.warning("ServiceNow live update failed (%s) - updating mock record", exc)
        rec = self.get_incident(number)
        if not rec:
            return None
        patch = {k: v for k, v in fields.items() if k != "work_notes"}
        if "work_notes" in fields:
            patch["work_notes"] = rec.get("work_notes", []) + [{"at": now(), "text": fields["work_notes"]}]
        patch["updated_at"] = now()
        self.store.update("sn_incidents", {"number": number}, patch)
        return self.get_incident(number)

    def create_request(self, p):
        if self.live:
            try:
                r = self._call("POST", "/sc_request", json={
                    "short_description": p["short_description"], "description": p["description"],
                    "requested_for": self._ref("sys_user", f"email={p['requested_for']}")})
                return {**p, "number": r["number"], "sys_id": r["sys_id"], "state": "Open", "mode": "live"}
            except Exception as exc:
                log.warning("ServiceNow live request failed (%s) - using mock", exc)
        n = self.store.count("sn_requests")
        rec = {**p, "number": f"REQ{1245 + n:06d}", "sys_id": uuid.uuid4().hex, "state": "Open",
               "opened_at": now(), "updated_at": now(), "mode": "mock"}
        self.store.insert("sn_requests", rec)
        return rec

    def update_request(self, number, fields):
        if self.live:
            try:
                sid = self._ref("sc_request", f"number={number}")
                self._call("PATCH", f"/sc_request/{sid}", json={k: v for k, v in fields.items() if k != "state"})
                return
            except Exception as exc:
                log.warning("ServiceNow live request update failed (%s)", exc)
        self.store.update("sn_requests", {"number": number}, {**fields, "updated_at": now()})
