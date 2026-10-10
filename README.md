# AI-Powered ITSM & Intelligent Helpdesk Automation Platform

Hackathon prototype: an employee asks for help in plain English and the platform **understands** the request,
**retrieves** approved knowledge (RAG), **acts** (self-heal / software provisioning), **records** it in ServiceNow and
an audit log, and **escalates to a human** when the AI is unsure.

```
React portal ──► FastAPI ──► Orchestrator ─┬─ Intent + incident classifier (rules, explainable)
 (4 screens)                               ├─ RAG: KB docs → chunks → embeddings → FAISS → LLM → sources
                                           ├─ Self-heal agent (allow-listed mock IAM/endpoint APIs + audit log)
                                           ├─ Software catalogue → ServiceNow REQ → mock provisioning API
                                           └─ ServiceNow client (live REST or mock) ──► MongoDB Atlas
```

## Quick start

**Backend** (Python 3.10+)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```
**Frontend** (Node 18+)
```bash
cd frontend && npm install && npm run dev
```
**Tests** (5 required scenarios + governance checks, hermetic: no network/models needed)
```bash
cd backend && pytest -v
```
With no `.env` the app still runs: in-memory store, mock ServiceNow, and (if models cannot download) TF-IDF
embeddings + extractive answers. The dashboard header and `/api/health` show which mode is active.
The first run downloads `all-MiniLM-L6-v2` (~90 MB) and `flan-t5-base` (~1 GB) from Hugging Face.

## Technology choices
| Component | Choice | Why |
|---|---|---|
| LLM | `google/flan-t5-base` (Apache-2.0, 250M) | Free, instruction-tuned for "answer from context" prompts, runs on a laptop CPU. Swap via `LLM_MODEL` (e.g. `google/flan-t5-large`). It only sees retrieved chunks. |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Small, fast, strong semantic similarity. TF-IDF fallback if unavailable. |
| Vector DB | FAISS `IndexFlatIP` (cosine on normalised vectors) | Zero-ops, exact search is plenty for a small KB. Numpy fallback if FAISS missing. |
| Database | MongoDB Atlas (`pymongo`) | Collections: `tickets, analyses, chat_history, kb_articles, software_requests, audit_logs, users, sn_incidents, sn_requests`. |
| ITSM | ServiceNow Table API, mock fallback | Same client interface for both; live failures fall back to mock. |

## RAG approach
1. `knowledge_base/*.md` — 8 articles (VPN, Password Reset, Account Lockout, Outlook, Wi-Fi, Laptop Performance, Software Installation, Application Access).
2. **Chunking**: section-aware (split on blank lines, merge ≤600 chars). 3. **Embedding** of `title + chunk`. 4. **FAISS** index built at startup (metadata in `kb_articles`).
5. **Search** returns top chunks + per-article similarity; **confidence** = best similarity ÷ model scale (0.7 MiniLM / 0.4 TF-IDF), capped at 0.99.
6. **LLM** receives only chunks scoring ≥ 50% of the best; answer shown with its **source articles**.

## AI safety & governance
- **No hallucination**: confidence below `CONFIDENCE_THRESHOLD` (default 0.5) → the answer is withheld and the UI says information is unavailable.
- **Source attribution**: every answer lists article, chunk id, similarity and confidence.
- **Human escalation**: low-confidence questions offer *Escalate to helpdesk*, which creates a ServiceNow incident (idempotent per conversation). `AUTO_ESCALATE=true` does this automatically.
- **Safe automation**: only actions on an allow-list run, and only if (a) the directory/endpoint diagnosis confirms the problem and (b) the KB backs the fix. Otherwise the incident stays open for a human (see the second "My password has expired." in the tests).
- **Audit log**: every intent decision, automation step, ticket and escalation is stored in `audit_logs` (`GET /api/audit`, shown on the dashboard).

## Scenario → what to demo
| # | Say this (portal chips) | Shows |
|---|---|---|
| 1 | "My VPN is not connecting." or the long VPN sentence | Classification (Network/VPN, P2, Individual/High, Network Support), RAG steps, ServiceNow INC created |
| 2 | "My password has expired." (as Asha Verma) | Identify → Diagnose → KB → Decide → Execute → Validate → ServiceNow Resolved; audit trail |
| 3 | "How do I troubleshoot Outlook synchronization?" | Vector search → LLM → answer + sources + confidence |
| 4 | "I need Visual Studio Code." | REQ number, ServiceNow request, mock provisioning → *Provisioning* → *Completed* (auto after 15 s, or click *complete* on the dashboard) |
| 5 | "What is the company policy on parental leave?" | No hallucination, escalation button → ServiceNow ticket |

Tip: use **Reset demo data** on the dashboard between runs (it re-arms the expired-password and locked-account users).
Other automations: "My account is locked" (as Ravi Nair), "Clear my Outlook cache", "Check VPN status", "Outlook is not responding".

## API (all under `/api`, interactive docs at `/docs`)
| Method & path | Purpose |
|---|---|
| `POST /chat` `{message, employee_id}` | Full pipeline; returns the AI analysis record |
| `POST /tickets/escalate` `{analysis_id}` | Human escalation → ServiceNow incident |
| `GET /tickets`, `GET /tickets/{INC}`, `PATCH /tickets/{INC}` | List / get (ServiceNow) / update incident |
| `GET /analyses`, `GET /analyses/{id}` | AI Analysis screen data |
| `GET /knowledge/articles`, `GET /knowledge/search?q=` | KB browse; RAG search with answer + hits |
| `GET /software/catalog`, `GET /software/requests`, `POST /software/requests/{REQ}/complete` | Provisioning |
| `GET /dashboard`, `GET /audit`, `GET /health`, `GET /employees`, `POST /demo/reset` | Dashboard, audit, config, demo helpers |

## ServiceNow integration
Set `SERVICENOW_INSTANCE` (e.g. `dev12345`), `SERVICENOW_USER`, `SERVICENOW_PASSWORD` (from a free Personal Developer Instance; never commit them).

| AI output | ServiceNow `incident` field |
|---|---|
| Summary | `short_description` |
| Employee text + AI note (confidence, suggested resolution) | `description` |
| Category / Sub-category | `category` / `subcategory` |
| Impact (Individual/Department/Enterprise) → 3/2/1 | `impact` |
| Urgency (High/Medium/Low) → 1/2/3 | `urgency` |
| Assignment group → looked up by name | `assignment_group` (sys_id) |
| Employee e-mail → looked up | `caller_id` (sys_id) |
| Resolve | `state=6`, `close_code`, `close_notes` |

Operations: Create (`POST /table/incident`), Get, Update (`PATCH`), Create Service Request (`POST /table/sc_request`).
Note: ServiceNow's default priority matrix derives priority from impact × urgency, so Individual/High usually
computes to P3 there; the mock stores the AI's P2 directly. In a real instance adjust the matrix or add a business rule.
Group names and category/subcategory values must exist in the instance's choice lists.

## Known limitations
- Intent/category/priority use transparent keyword rules (deterministic for demos); an LLM zero-shot classifier is the natural next step.
- Password reset, unlock, cache, VPN and restart actions are **mocks**; production would call Entra ID/AD, Intune/SCCM and the VPN gateway.
- Live ServiceNow path is implemented but only the mock is covered by tests. No authentication on the portal (employee selector is for demo).
- `flan-t5-base` gives short answers; use a larger model for richer prose. Extractive fallback is used if the model can't load.

## Future improvements
Streaming answers, LLM-based classification with confidence calibration, feedback loop (thumbs up/down → KB gaps), SSO,
approval workflow for licensed software, ServiceNow webhooks for status sync, Qdrant for multi-tenant scale.
