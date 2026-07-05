# Incoming Request Processing Workflow

An AI prototype that receives incoming operational requests for a telecom operator ("Orbit Mobile"), classifies them by **type** and **urgency**, and runs a distinct multi-step remediation workflow for each type - routing, drafting responses, logging, SLA tracking, and human-in-the-loop approval where needed.

Built as a 5-day STEM POC. Scope is deliberately narrow: get four request types working reliably end-to-end (classification -> automated actions -> delivery -> visibility).

## Overview

A request comes in (web form, email, or manually via the Console), and the system:

1. **Classifies** it into one of 4 types + an urgency level, using an LLM (Gemini)
2. **Runs branch-specific logic** - a different set of automated actions per type
3. **Delivers** the result - Slack notifications routed to the right team, and email replies/confirmations
4. **Logs** everything to a database, visible in a Console (case queue + human approval) and a Dashboard (aggregate metrics)

```
Web Form  --\
Email     ---> n8n (triggers) --> POST /process --> FastAPI
Console   --/                                          |
                                                        | 1. classify
                                                        | 2. branch logic
                                                        | 3. save to DB
                                                        v
                                              POST webhook (case data)
                                                        |
                                                        v
                                              n8n (delivery workflow)
                                                |               |
                                                v               v
                                     Slack (routed by       Email (Mailtrap,
                                     department/queue)      subscriber replies)

Streamlit Console   --> GET/POST /console/*  --> case queue, human approval, edit-before-send
Streamlit Dashboard --> GET /console/cases   --> volume/status/SLA/confidence charts
```

**Why this split:** FastAPI owns all reasoning (classification, RAG, branch logic) and is the single source of truth (Turso/libSQL). n8n owns only orchestration (webhook triggers, Slack, email). If n8n breaks, the reasoning and data layer are unaffected and only delivery pauses.

## The 4 branches

| Type | Urgency | Automated actions | Approval needed? |
|---|---|---|---|
| **Enquiry** | Low | RAG-grounded answer (ChromaDB knowledge base) generated and emailed automatically; logged resolved | No |
| **Service Request** | Medium | Summarized, routed to one of 5 departments (Billing, Technical Support, SIM & Number Porting, Plan Changes, Network Operations) via a dedicated Slack channel; confirmation emailed; 4h SLA timer set | No |
| **Complaint** | High | Escalated to `#complaints-queue` channel in Slack; empathetic acknowledgement drafted; 2h SLA reminder set | **Yes** - held until a human approves in the Console (draft is editable before sending) |
| **Escalation** | Critical | Flagged to `#escalations-queue` channel in Slack for immediate human attention; urgent acknowledgement drafted; no automated resolution  | **Yes** - same approval gate as Complaint |

Classification uses a single LLM call (Gemini `gemini-3.1-flash-lite`) returning structured JSON: `{type, urgency, confidence}`. Department selection for Service Request is also LLM-driven but constrained to a fixed enum (validated server-side with a fallback), so Slack routing is deterministic.

## Project structure

```
api/                        FastAPI service - all classification & branch logic
  main.py                   App entrypoint, router registration, DB init
  routers/
    process.py              POST /process - the main entry point for all channels
    console.py               /console/* - case queue, case detail, approve/reject
  services/
    classification.py       LLM classification prompt + validation
    branch_actions.py        Per-type branch logic (RAG call, department routing, drafts)
    rag.py                   ChromaDB retrieval for the enquiry branch
  models/schema.py          Pydantic request/response models
  db/database.py            Turso (libSQL) persistence layer
  utils/file_extraction.py  .txt/.eml/.pdf/.docx text extraction for file uploads

console/                    Streamlit operator UI
  app.py                    Landing page
  formatting.py             Shared local-time formatting helper
  pages/console.py          Submit-request form + case queue + case detail/approval
  pages/dashboard.py        Aggregate volume/status/SLA/confidence charts

n8n/
  workflow_export.json            Delivery workflow: routes each processed case to
                                   Slack (department/queue-specific channels) and email
                                   (Mailtrap), plus the post-approval send
  workflow_inbound_triggers.json  Inbound entry points: a public web form (n8n Form
                                   Trigger) and an IMAP-polled support inbox, both
                                   forwarding into POST /process

rag/
  build_knowledge_base.py   Indexes rag/knowledge_base/faq.json into a Chroma collection
  knowledge_base/faq.json   Curated telecom FAQ chunks (plans, billing, roaming, etc.)

data/
  sample_inputs/            One sample request per branch (see below)
  sample_outputs/           Corresponding captured API responses
```

## Setup

### Prerequisites

- Python 3.11+
- Docker (for n8n)
- A [Turso](https://turso.tech) database (libSQL)
- A [Gemini API key](https://ai.google.dev)
- A Mailtrap account (Email Testing sandbox) - for outbound email delivery
- A Slack workspace where you can create an app + channels

### 1. API

```bash
cd api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in GEMINI_API_KEY, TURSO_DATABASE_URL, TURSO_AUTH_TOKEN
uvicorn main:app --reload --port 8000
```

### 2. Build the RAG knowledge base

```bash
cd rag
pip install chromadb   # if not already in your environment
python3 build_knowledge_base.py
```

This indexes `rag/knowledge_base/faq.json` into a local Chroma collection used by the enquiry branch.

### 3. Console

```bash
cd console
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # API_BASE_URL, defaults to http://localhost:8000
streamlit run app.py
```

### 4. n8n

```bash
docker run -it --rm -p 5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
```

Then in the n8n UI (http://localhost:5678):

1. Import **`n8n/workflow_export.json`** (delivery) and **`n8n/workflow_inbound_triggers.json`** (inbound triggers)
2. Create credentials:
   - **SMTP** named `Mailtrap SMTP` - host/port/user/password from your Mailtrap inbox's SMTP tab
   - **Header Auth** named `Slack Bot Token` - header `Authorization`, value `Bearer xoxb-...` (a Slack app with `chat:write` + `chat:write.public` scopes)
   - **IMAP** named `Gmail IMAP` (or your provider) - for the inbound email trigger, if you want that channel live
3. Create the Slack channels referenced in the routing map: `#billing-ops`, `#technical-support-ops`, `#sim-porting-ops`, `#plan-changes-ops`, `#network-ops`, `#complaints-queue`, `#escalations-queue` (rename to taste, just keep the mapping in `workflow_export.json`'s Slack nodes in sync)
4. **Activate** both workflows
5. Set `N8N_PROCESS_WEBHOOK_URL` and `N8N_APPROVAL_WEBHOOK_URL` in `api/.env` to point at your n8n instance (defaults assume `localhost:5678`)

## API reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/process` | POST | Submit a request (`source`, `request_text` **or** `file`,  `requester_email`) - classifies, runs branch logic, persists, triggers delivery |
| `/console/cases` | GET | List all cases |
| `/console/cases/{id}` | GET | Get one case |
| `/console/cases/{id}/approve` | POST | Approve/reject a pending case; accepts an optional `edited_draft` to override the AI-drafted acknowledgement before it's sent |

## Sample inputs & outputs

One example per branch, in [`data/sample_inputs/`](data/sample_inputs) and [`data/sample_outputs/`](data/sample_outputs):

| Branch | Input | Output |
|---|---|---|
| Enquiry | [`01_enquiry.txt`](data/sample_inputs/01_enquiry.txt) | [`01_enquiry.json`](data/sample_outputs/01_enquiry.json) |
| Service Request | [`02_service_request.txt`](data/sample_inputs/02_service_request.txt) | [`02_service_request.json`](data/sample_outputs/02_service_request.json) |
| Complaint | [`03_complaint.txt`](data/sample_inputs/03_complaint.txt) | [`03_complaint.json`](data/sample_outputs/03_complaint.json) |
| Escalation | [`04_escalation.txt`](data/sample_inputs/04_escalation.txt) | [`04_escalation.json`](data/sample_outputs/04_escalation.json) |

Try one yourself:

```bash
curl -X POST http://localhost:8000/process \
  -F "source=web_form" \
  -F "requester_email=test@example.com" \
  -F "request_text=$(cat data/sample_inputs/01_enquiry.txt)"
```

## Known limitations

- **Classification is LLM-only** - no second trained classifier (embeddings + logistic regression/XGBoost) is used alongside it, per an intentional scope cut for this POC.
- **SLA deadlines are tracked, not enforced** - `sla_deadline` is stored and surfaced in the Console/Dashboard, but nothing automatically fires a reminder or escalates on breach (no n8n Wait node).
- **Gemini free-tier rate limits** - the free tier caps at 15 requests/minute for `gemini-3.1-flash-lite`; heavy demo traffic can hit `429` errors.
- **Local-time display uses a fixed UTC+10 offset** rather than true browser timezone detection, since Streamlit can't read that server-side.
- **Mailtrap sandbox** - outbound emails land in a Mailtrap sandbox inbox, not real subscriber inboxes, by design (safe for a demo).
