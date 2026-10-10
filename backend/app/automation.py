import re

from . import audit, config, services, tickets
from .db import now


def _user(emp):
    return services.store.find("users", {"employee_id": emp})[0]


def _set(emp, patch):
    services.store.update("users", {"employee_id": emp}, patch)


def d_password(u):
    exp = u.get("password_expired")
    return exp, f"Directory lookup for {u['employee_id']}: password status = {'EXPIRED' if exp else 'valid'}"


def e_password(u):
    _set(u["employee_id"], {"password_expired": False})
    return True, "Mock IAM API: password reset executed; temporary credential sent to registered mobile (must be changed at next sign-in)"


def v_password(u):
    ok = not _user(u["employee_id"])["password_expired"]
    return ok, "Directory re-check: password status = valid" if ok else "Password still expired"


def d_unlock(u):
    return u.get("locked"), f"Directory lookup for {u['employee_id']}: account status = {'LOCKED' if u.get('locked') else 'active'}"


def e_unlock(u):
    _set(u["employee_id"], {"locked": False})
    return True, "Mock IAM API: account unlocked"


def v_unlock(u):
    ok = not _user(u["employee_id"])["locked"]
    return ok, "Directory re-check: account status = active" if ok else "Account still locked"


ACTIONS = {
    "password_reset": {"label": "Expired password reset", "action": "reset_password",
                       "regex": r"password.*(expire|reset|forgot|forgotten|change)|(forgot|forgotten|expired).*password",
                       "diagnose": d_password, "execute": e_password, "validate": v_password,
                       "note": "Password reset automatically by AI self-heal agent after identity and directory check."},
    "account_unlock": {"label": "Account unlock", "action": "unlock_account",
                       "regex": r"locked out|account.*lock|lock.*account|unlock",
                       "diagnose": d_unlock, "execute": e_unlock, "validate": v_unlock,
                       "note": "Account unlocked automatically by AI self-heal agent."},
    "clear_cache": {"label": "Outlook cache clear", "action": "clear_cache",
                    "regex": r"clear.*cache|cache.*(clear|corrupt|full)",
                    "diagnose": lambda u: (True, "Endpoint API: Outlook cache is 1.8 GB (above 1 GB threshold)"),
                    "execute": lambda u: (True, "Mock endpoint API: Outlook cache cleared, 1.6 GB freed"),
                    "validate": lambda u: (True, "Endpoint API: cache size now 0.2 GB"),
                    "note": "Outlook cache cleared automatically by AI self-heal agent."},
    "vpn_status": {"label": "VPN status check", "action": "vpn_status_check",
                   "regex": r"(check|status).*vpn|vpn.*(status|reachable)|is (the )?vpn (down|up)",
                   "diagnose": lambda u: (True, "VPN gateway probe: gateway UP; user session: not established"),
                   "execute": lambda u: (True, "Mock VPN API: stale session cleared, gateway healthy"),
                   "validate": lambda u: (True, "VPN API: user can re-establish a session"),
                   "note": "VPN gateway checked and stale session cleared by AI self-heal agent."},
    "restart_app": {"label": "Application restart", "action": "restart_application",
                    "regex": r"restart.*(app|application|outlook|teams|zoom)|(outlook|teams|zoom|app|application).*(frozen|not responding|hung|stuck)",
                    "diagnose": lambda u: (True, "Endpoint API: application process not responding"),
                    "execute": lambda u: (True, "Mock endpoint API: restart command sent"),
                    "validate": lambda u: (True, "Endpoint API: process running and responsive"),
                    "note": "Application restarted automatically by AI self-heal agent."},
}
SAFE_ACTIONS = set(ACTIONS)


def match(text):
    for key, spec in ACTIONS.items():
        if re.search(spec["regex"], text, re.I):
            return key
    return None


def run(a, message, user, key, fields, kb_res):
    spec, steps = ACTIONS[key], []

    def step(name, status, detail, **meta):
        steps.append({"step": name, "status": status, "detail": detail, "at": now()})
        audit.log(f"self_heal.{name.lower().replace(' ', '_')}", "self-heal-agent", user["employee_id"], detail,
                  status="success" if status in ("ok", "skipped") else status, ticket=ticket["number"] if ticket else None,
                  analysis_id=a["analysis_id"], meta={"automation": key, **meta})

    ticket = None
    audit.log("self_heal.identify", "self-heal-agent", user["employee_id"],
              f"Issue identified as '{spec['label']}' for {user['name']}", analysis_id=a["analysis_id"], meta={"automation": key})
    ticket = tickets.create(a, fields, user, note="Auto-created by AI self-heal agent", source="ai_incident")
    steps.append({"step": "Identify", "status": "ok", "at": now(),
                  "detail": f"Issue identified as '{spec['label']}'; ServiceNow incident {ticket['number']} opened"})

    confirmed, detail = spec["diagnose"](user)
    step("Diagnose", "ok" if confirmed else "failed", detail)

    conf, top = kb_res["confidence"], (kb_res["sources"][0]["title"] if kb_res["sources"] else None)
    kb_ok = conf >= config.CONFIDENCE_THRESHOLD and top is not None
    step("Knowledge Search", "ok" if kb_ok else "warn",
         f"Approved fix found in '{top}' (confidence {conf})" if kb_ok else f"No approved KB procedure (confidence {conf})")

    safe = key in SAFE_ACTIONS and confirmed and kb_ok
    step("Determine Automation", "ok" if safe else "skipped",
         f"Action '{spec['action']}' is on the safe allow-list and backed by the KB" if safe
         else "Not safe to automate (problem not confirmed or no KB backing) - leaving for a human agent")

    resolved = False
    if safe:
        ok, detail = spec["execute"](user)
        step("Execute", "ok" if ok else "failed", detail)
        audit.log("self_heal.execute", "self-heal-agent", user["employee_id"], f"{spec['action']}: {detail}",
                  status="success" if ok else "failed", ticket=ticket["number"], analysis_id=a["analysis_id"],
                  meta={"automation": key})
        ok, vdetail = spec["validate"](user)
        step("Validate", "ok" if ok else "failed", vdetail)
        if ok:
            tickets.resolve(ticket["number"], spec["note"])
            step("Update ServiceNow", "ok", f"{ticket['number']} set to Resolved with close notes")
            resolved = True
    if not resolved:
        services.sn.update_incident(ticket["number"], {"work_notes": "AI could not safely auto-resolve; assigned to human agent."})
        step("Update ServiceNow", "ok", f"{ticket['number']} left open for {ticket['assignment_group']}")
    ticket_state = "Resolved" if resolved else ticket["state"]
    return {"status": "resolved" if resolved else "not_automated", "action": spec["action"], "label": spec["label"],
            "steps": steps, "ticket": {**tickets.ref(ticket), "state": ticket_state}}
