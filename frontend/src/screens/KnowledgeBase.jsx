import { useEffect, useState } from "react";
import { api } from "../api";
import { Confidence, Icon, Modal, Pill } from "../components/ui.jsx";

const CAT_ICON = { Network: "bolt", Access: "shield", Email: "chat", Hardware: "dashboard", Software: "package" };

export default function KnowledgeBase() {
  const [articles, setArticles] = useState([]);
  const [cat, setCat] = useState("All");
  const [open, setOpen] = useState(null);
  const [q, setQ] = useState("");
  const [res, setRes] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.articles().then(setArticles);
  }, []);

  const cats = ["All", ...new Set(articles.map((a) => a.category))];
  const shown = articles.filter((a) => cat === "All" || a.category === cat);

  async function search(text) {
    const query = (text ?? q).trim();
    if (query.length < 2) return;
    setQ(query);
    setLoading(true);
    try {
      setRes(await api.search(query));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="stack">
      <div className="card hero search-hero">
        <h3>Semantic search with grounded answers</h3>
        <p className="muted">Query is embedded, matched against the vector index, then answered only from retrieved articles.</p>
        <div className="big-search">
          <Icon name="search" />
          <input value={q} placeholder="Try: How do I fix Outlook sync?" onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} />
          <button className="btn primary" onClick={() => search()} disabled={loading}>{loading ? "Searching..." : "Search"}</button>
        </div>
        <div className="suggest">
          {["VPN authentication keeps failing", "How do I fix Outlook sync?", "Wi-Fi will not connect", "request access to an application"].map((s) => (
            <button key={s} className="chip-btn" onClick={() => search(s)}>{s}</button>
          ))}
        </div>
      </div>

      {res && (
        <div className="grid2 wide-left">
          <div className="card">
            <h3>Answer <Pill tone={res.grounded ? "success" : "danger"}>{res.grounded ? "Grounded" : "Insufficient KB content"}</Pill></h3>
            <Confidence value={res.confidence} threshold={res.threshold} />
            <pre>{res.answer}</pre>
            <p className="muted">{res.vector_db} · {res.embedding_model.split("/").pop()} · {res.answer_model || "no generation"}</p>
          </div>
          <div className="card">
            <h3>Retrieved chunks</h3>
            {res.hits.length === 0 && <p className="muted">Nothing relevant was retrieved.</p>}
            {res.hits.map((h) => (
              <div key={h.chunk_id} className="hit">
                <div className="hit-head">
                  <b>{h.title}</b>
                  <Pill tone="primary">{h.chunk_id}</Pill>
                </div>
                <div className="sim"><div style={{ width: `${Math.min(100, h.score * 130)}%` }} /></div>
                <div className="muted">Similarity {h.score}</div>
                <pre>{h.text}</pre>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <div className="section-head">
          <h3>Articles</h3>
          <div className="chips">
            {cats.map((c) => (
              <button key={c} className={c === cat ? "chip-btn active" : "chip-btn"} onClick={() => setCat(c)}>{c}</button>
            ))}
          </div>
        </div>
        <div className="article-grid">
          {shown.map((a) => (
            <button key={a.article_id} className="article" onClick={() => setOpen(a)}>
              <span className="a-icon"><Icon name={CAT_ICON[a.category] || "file"} /></span>
              <b>{a.title}</b>
              <Pill>{a.category}</Pill>
              <span className="muted">{a.content.length} characters</span>
            </button>
          ))}
        </div>
      </div>

      {open && (
        <Modal title={open.title} onClose={() => setOpen(null)}>
          <Pill tone="primary">{open.category}</Pill>
          <pre>{open.content}</pre>
        </Modal>
      )}
    </div>
  );
}
