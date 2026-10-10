import logging
import re

import numpy as np

from . import config

log = logging.getLogger("itsm.rag")

STOP = set("a an the and or of to in on for with is are was were be been it this that my i me we you your our at "
           "by from as if do does did how what where when which who can could should would will not no yes there "
           "their they them its into about".split())


def _stem(w):
    for suf in ("ing", "ion", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            w = w[: -len(suf)]
            break
    return w[:-1] if w.endswith("e") and len(w) > 4 else w


def analyzer(text):
    toks = [_stem(t) for t in re.findall(r"[a-z0-9]+", text.lower().replace("wi-fi", "wifi")) if t not in STOP and len(t) > 1]
    return toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]


def _norm(m):
    return m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)


def parse_doc(path):
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    title, category, body = lines[0].lstrip("# ").strip(), "General", []
    for line in lines[1:]:
        if line.lower().startswith("category:"):
            category = line.split(":", 1)[1].strip()
        else:
            body.append(line)
    return {"article_id": path.stem, "title": title, "category": category, "content": "\n".join(body).strip()}


def chunk(text, max_chars=600):
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) > max_chars:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        chunks.append(cur)
    return chunks


class TfidfEmbedder:
    name, scale = "tfidf-fallback", 0.4

    def fit(self, texts):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.v = TfidfVectorizer(analyzer=analyzer, sublinear_tf=True)
        return _norm(self.v.fit_transform(texts).toarray().astype("float32"))

    def encode(self, texts):
        return _norm(self.v.transform(texts).toarray().astype("float32"))


class STEmbedder:
    scale = 0.7

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.name = config.EMBEDDING_MODEL
        self.model = SentenceTransformer(config.EMBEDDING_MODEL)

    def fit(self, texts):
        return self.encode(texts)

    def encode(self, texts):
        return np.asarray(self.model.encode(texts, normalize_embeddings=True), dtype="float32")


class VectorIndex:

    def __init__(self, vecs):
        self.vecs = np.ascontiguousarray(vecs, dtype="float32")
        try:
            import faiss
            self.index = faiss.IndexFlatIP(self.vecs.shape[1])
            self.index.add(self.vecs)
            self.engine = "faiss"
        except Exception:
            self.index, self.engine = None, "numpy"

    def search(self, q, k):
        q = np.ascontiguousarray(q, dtype="float32")
        if self.index is not None:
            s, i = self.index.search(q, k)
            return s[0], i[0]
        s = self.vecs @ q[0]
        idx = np.argsort(-s)[:k]
        return s[idx], idx


class KnowledgeBase:
    def __init__(self):
        self.articles, self.chunks, self.index, self.embedder = [], [], None, None

    def _make_embedder(self):
        pref = config.EMBEDDING_BACKEND
        if pref in ("auto", "st"):
            try:
                return STEmbedder()
            except Exception as exc:
                if pref == "st":
                    raise
                log.warning("sentence-transformers unavailable (%s) - using TF-IDF fallback", exc)
        return TfidfEmbedder()

    def build(self):
        self.articles = [parse_doc(p) for p in sorted(config.KB_DIR.glob("*.md"))]
        self.chunks = []
        for a in self.articles:
            for i, c in enumerate(chunk(a["content"])):
                self.chunks.append({"chunk_id": f"{a['article_id']}#{i}", "article_id": a["article_id"],
                                    "title": a["title"], "category": a["category"], "text": c})
        self.embedder = self._make_embedder()
        vecs = self.embedder.fit([f"{c['title']}. {c['text']}" for c in self.chunks])
        self.index = VectorIndex(vecs)
        log.info("KB built: %d articles, %d chunks, embeddings=%s, index=%s", len(self.articles),
                 len(self.chunks), self.embedder.name, self.index.engine)

    def article_metadata(self):
        return [{"article_id": a["article_id"], "title": a["title"], "category": a["category"],
                 "chunks": sum(1 for c in self.chunks if c["article_id"] == a["article_id"]),
                 "embedding_model": self.embedder.name} for a in self.articles]

    def info(self):
        return {"articles": len(self.articles), "chunks": len(self.chunks),
                "embedding_model": self.embedder.name, "vector_db": self.index.engine}

    def search(self, query, k=4):
        qv = self.embedder.encode([query])
        scores, idxs = self.index.search(qv, min(k, len(self.chunks)))
        hits = []
        for s, i in zip(scores, idxs):
            if int(i) < 0 or float(s) <= 0:
                continue
            hits.append({**self.chunks[int(i)], "score": round(float(s), 3)})
        top = hits[0]["score"] if hits else 0.0
        hits = [h for h in hits if h["score"] >= 0.5 * top][:3]
        sources, seen = [], set()
        for h in hits:
            if h["article_id"] not in seen:
                seen.add(h["article_id"])
                sources.append({"article_id": h["article_id"], "title": h["title"], "category": h["category"],
                                "chunk_id": h["chunk_id"], "score": h["score"],
                                "confidence": round(min(0.99, h["score"] / self.embedder.scale), 2)})
        return {"hits": hits, "sources": sources, "confidence": round(min(0.99, top / self.embedder.scale), 2)}
