import copy
import logging
import threading
from datetime import datetime, timezone

from . import config

log = logging.getLogger("itsm.db")

COLLECTIONS = ["users", "tickets", "analyses", "chat_history", "kb_articles", "software_requests",
               "audit_logs", "sn_incidents", "sn_requests"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _match(doc, query):
    return all(doc.get(k) == v for k, v in (query or {}).items())


class MemoryStore:
    backend = "in-memory"

    def __init__(self):
        self._c, self._lock = {}, threading.Lock()

    def insert(self, coll, doc):
        with self._lock:
            self._c.setdefault(coll, []).append(copy.deepcopy(doc))
        return doc

    def find(self, coll, query=None, sort=None, limit=0):
        with self._lock:
            rows = [copy.deepcopy(d) for d in self._c.get(coll, []) if _match(d, query)]
        if sort:
            rows.sort(key=lambda d: d.get(sort[0], ""), reverse=sort[1] < 0)
        return rows[:limit] if limit else rows

    def update(self, coll, query, patch):
        with self._lock:
            for d in self._c.get(coll, []):
                if _match(d, query):
                    d.update(copy.deepcopy(patch))
                    return True
        return False

    def count(self, coll, query=None):
        return len(self.find(coll, query))

    def clear(self, coll):
        with self._lock:
            self._c[coll] = []


class MongoStore:
    backend = "mongodb-atlas"

    def __init__(self, uri, dbname):
        from pymongo import MongoClient
        self.db = MongoClient(uri, serverSelectionTimeoutMS=5000)[dbname]
        self.db.command("ping")

    def insert(self, coll, doc):
        self.db[coll].insert_one(dict(doc))
        return doc

    def find(self, coll, query=None, sort=None, limit=0):
        cur = self.db[coll].find(query or {}, {"_id": 0})
        if sort:
            cur = cur.sort(sort[0], sort[1])
        if limit:
            cur = cur.limit(limit)
        return list(cur)

    def update(self, coll, query, patch):
        return self.db[coll].update_one(query, {"$set": patch}).matched_count > 0

    def count(self, coll, query=None):
        return self.db[coll].count_documents(query or {})

    def clear(self, coll):
        self.db[coll].delete_many({})


_store = None


def get_store():
    global _store
    if _store is None:
        if config.MONGODB_URI:
            try:
                _store = MongoStore(config.MONGODB_URI, config.MONGODB_DB)
                log.info("Connected to MongoDB Atlas")
            except Exception as exc:
                log.warning("MongoDB unavailable (%s) - falling back to in-memory store", exc)
                _store = MemoryStore()
        else:
            _store = MemoryStore()
    return _store
