from . import db
from .rag import KnowledgeBase
from .servicenow import ServiceNowClient

store = None
kb = None
sn = None

SEED_USERS = [
    {"employee_id": "emp001", "name": "Asha Verma", "email": "asha.verma@corp.example", "department": "Engineering",
     "password_expired": True, "locked": False},
    {"employee_id": "emp002", "name": "Ravi Nair", "email": "ravi.nair@corp.example", "department": "Finance",
     "password_expired": False, "locked": True},
    {"employee_id": "emp003", "name": "Meera Iyer", "email": "meera.iyer@corp.example", "department": "HR",
     "password_expired": False, "locked": False},
]


def seed_users():
    store.clear("users")
    for u in SEED_USERS:
        store.insert("users", dict(u))


def init():
    global store, kb, sn
    store = db.get_store()
    kb = KnowledgeBase()
    kb.build()
    sn = ServiceNowClient(store)
    if store.count("users") == 0:
        seed_users()
    store.clear("kb_articles")
    for a in kb.article_metadata():
        store.insert("kb_articles", a)


def reset_demo():
    for coll in db.COLLECTIONS:
        if coll != "kb_articles":
            store.clear(coll)
    seed_users()
