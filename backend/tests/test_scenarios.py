import os

os.environ.update({"USE_LLM": "false", "EMBEDDING_BACKEND": "tfidf", "MONGODB_URI": "", "SERVICENOW_INSTANCE": ""})

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        c.post("/api/demo/reset")
        yield c


def chat(client, msg, emp="emp001"):
    r = client.post("/api/chat", json={"message": msg, "employee_id": emp})
    assert r.status_code == 200, r.text
    return r.json()


def test_1_intelligent_ticket_intake(client):
    a = chat(client, "I cannot connect to VPN since this morning. Authentication keeps failing.")
    assert a["intent"] == "Incident"
    assert (a["category"], a["subcategory"]) == ("Network", "VPN")
    assert a["priority"] == "P2"
    assert (a["impact"], a["urgency"]) == ("Individual", "High")
    assert a["assignment_group"] == "Network Support"
    assert a["summary"] == "VPN authentication failure"
    assert "VPN" in a["suggested_resolution"]
    assert a["ticket"]["number"].startswith("INC")
    assert a["sources"] and a["steps"]
    inc = client.get(f"/api/tickets/{a['ticket']['number']}").json()["servicenow"]
    assert inc["short_description"] == "VPN authentication failure" and inc["state"] == "New"


def test_1b_short_vpn_message(client):
    a = chat(client, "My VPN is not connecting.")
    assert a["intent"] == "Incident" and a["subcategory"] == "VPN" and a["ticket"]


def test_2_self_healing_password(client):
    a = chat(client, "My password has expired.")
    assert a["intent"] == "Automatable Issue"
    assert a["automation"]["status"] == "resolved"
    names = [s["step"] for s in a["automation"]["steps"]]
    assert names == ["Identify", "Diagnose", "Knowledge Search", "Determine Automation", "Execute", "Validate", "Update ServiceNow"]
    assert all(s["status"] == "ok" for s in a["automation"]["steps"])
    num = a["ticket"]["number"]
    assert client.get(f"/api/tickets/{num}").json()["servicenow"]["state"] == "Resolved"
    audit = [l for l in client.get("/api/audit").json() if l["ticket"] == num]
    assert len(audit) >= 6 and any(l["action"] == "self_heal.execute" for l in audit)
    b = chat(client, "My password has expired.")
    assert b["automation"]["status"] == "not_automated"


def test_3_rag_with_sources(client):
    a = chat(client, "How do I troubleshoot Outlook synchronization?")
    assert a["intent"] == "Knowledge Question"
    assert a["sources"][0]["article_id"] == "outlook-sync"
    assert a["confidence"] >= a["confidence_threshold"]
    assert a["ticket"] is None and "cache" in a["response"].lower()


def test_4_software_provisioning(client):
    a = chat(client, "I need Visual Studio Code installed on my laptop.")
    assert a["intent"] == "Service Request"
    sr = a["software_request"]
    assert sr["request_id"].startswith("REQ") and sr["software"] == "Visual Studio Code"
    assert sr["status"] == "Provisioning"
    done = client.post(f"/api/software/requests/{sr['request_id']}/complete").json()
    assert done["status"] == "Completed"
    b = chat(client, "I need Microsoft Visio")
    assert b["software_request"]["status"] == "Pending Approval"


def test_5_unknown_question_no_hallucination(client):
    a = chat(client, "What is the company policy on parental leave?")
    assert a["sources"] == [] and a["escalation_recommended"] is True and a["ticket"] is None
    assert "won't guess" in a["response"]
    e = client.post("/api/tickets/escalate", json={"analysis_id": a["analysis_id"]}).json()
    assert e["escalated"] is True and e["ticket"]["number"].startswith("INC")
    again = client.post("/api/tickets/escalate", json={"analysis_id": a["analysis_id"]}).json()
    assert again["ticket"]["number"] == e["ticket"]["number"]


def test_servicenow_update_and_dashboard(client):
    a = chat(client, "My laptop is very slow and freezing")
    num = a["ticket"]["number"]
    r = client.patch(f"/api/tickets/{num}", json={"state": "In Progress", "work_notes": "Picked up"})
    assert r.json()["state"] == "In Progress"
    d = client.get("/api/dashboard").json()
    assert d["kpis"]["ai_resolved"] >= 1 and d["kpis"]["escalated"] >= 1
    assert d["kpis"]["software_requests"] >= 2 and d["automation"]["executed"] >= 1


def test_kb_search_endpoint(client):
    r = client.get("/api/knowledge/search", params={"q": "my wifi will not connect"}).json()
    assert r["grounded"] and r["sources"][0]["article_id"] == "wifi-connectivity"
    r = client.get("/api/knowledge/search", params={"q": "best pizza topping"}).json()
    assert not r["grounded"]
