import re

from . import automation, software

KNOWLEDGE_START = re.compile(r"^\s*(how|what|where|which|who|explain|tell me|can you explain)\b", re.I)
INSTALL = re.compile(r"\b(install|installed|installation|provision|set ?up)\b", re.I)
WANT = re.compile(r"\b(need|want|request|requesting|require|get|please)\b", re.I)
ISSUE = re.compile(r"\b(cannot|can't|cant|unable|won't|wont|doesn't|failed|failing|fails|failure|error|down|crash\w*|"
                   r"slow|frozen|freez\w*|locked|expired|keeps|stuck|broken|issue|problem)\b|"
                   r"\b(not|isn't|aren't|won't)\s+(connect\w*|work\w*|load\w*|sync\w*|open\w*|respond\w*)", re.I)

CATEGORIES = [
    ("Network", "VPN", r"\bvpn\b|anyconnect|remote access", "Network Support"),
    ("Network", "Wi-Fi", r"wi-?fi|wireless|internet|network connection", "Network Support"),
    ("Email", "Outlook", r"outlook|e-?mail|mailbox|calendar|\bsync", "Messaging Support"),
    ("Hardware", "Laptop Performance", r"laptop|slow|freez|performance|\bcpu\b|battery|\bfan\b", "Desktop Support"),
    ("Access", "Password / Account", r"password|account|login|log in|locked|authenticat|\bmfa\b", "Identity & Access Management"),
    ("Software", "Installation", r"install|software|licen[cs]e", "Software Support"),
    ("Access", "Application Access", r"access to|permission|\brole\b|unauthori[sz]ed|application access", "Application Support"),
]

URGENT = re.compile(r"cannot|can't|unable|not (connecting|working)|keeps failing|failing|failed|locked out|urgent|asap|"
                    r"since (this )?morning|blocked|\bdown\b|critical|won't", re.I)
LOW = re.compile(r"\b(minor|when you can|no rush|low priority|cosmetic)\b", re.I)
ENTERPRISE = re.compile(r"company[- ]wide|entire (company|organi[sz]ation)|all employees|outage|production", re.I)
DEPARTMENT = re.compile(r"\b(everyone|all users|whole (team|office|department)|our team|my team|"
                        r"entire (team|office|department)|multiple users)\b", re.I)


def detect_intent(msg):
    if KNOWLEDGE_START.search(msg):
        return "Knowledge Question", 0.85, "Starts with a question word (how/what/where...)"
    sw = software.find(msg)
    if not ISSUE.search(msg) and ((sw and (WANT.search(msg) or INSTALL.search(msg))) or (INSTALL.search(msg) and WANT.search(msg))):
        return "Service Request", 0.9 if sw else 0.7, ("Software request matched catalogue item '%s'" % sw["name"]) if sw else "Install request, item not in catalogue"
    key = automation.match(msg)
    if key:
        return "Automatable Issue", 0.9, f"Matches safe automation '{automation.ACTIONS[key]['label']}'"
    if ISSUE.search(msg):
        return "Incident", 0.85, "Describes a failure/problem (cannot, not working, error...)"
    return "Knowledge Question", 0.5, "No incident, request or automation pattern - treated as a knowledge lookup"


def classify_incident(msg):
    category, sub, group, matched = "General", "Other", "Service Desk", False
    for c, s, rx, g in CATEGORIES:
        if re.search(rx, msg, re.I):
            category, sub, group, matched = c, s, g, True
            break
    impact = "Enterprise" if ENTERPRISE.search(msg) else "Department" if DEPARTMENT.search(msg) else "Individual"
    urgency = "High" if URGENT.search(msg) else "Low" if LOW.search(msg) else "Medium"
    if impact == "Enterprise":
        priority = "P1"
    elif impact == "Department":
        priority = "P1" if urgency == "High" else "P2"
    else:
        priority = {"High": "P2", "Medium": "P3", "Low": "P4"}[urgency]
    return {"category": category, "subcategory": sub, "assignment_group": group, "matched": matched,
            "impact": impact, "urgency": urgency, "priority": priority, "summary": _summary(msg, sub)}


def _summary(msg, sub):
    m = msg.lower()
    if sub == "VPN":
        if re.search(r"authent|login|credential|password", m):
            return "VPN authentication failure"
        if re.search(r"connect|unable|cannot|can't", m):
            return "VPN connection failure"
        return "VPN issue"
    first = re.split(r"[.!?]", msg.strip())[0].strip()
    return (first[:80] + "...") if len(first) > 80 else (first or "Employee-reported issue")
