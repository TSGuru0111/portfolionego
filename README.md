# PortfolioNarrator

AI-powered quarterly and monthly portfolio commentary platform for Indian wealth management firms, PMS providers, and RIAs.

> Generates personalised, 7-section RM letters from live portfolio data, market context, and stock-specific news using Cohere Command R+ — in under 60 seconds per client.

---

## Repository layout

```
.
├── backend/             FastAPI + Cohere + Supabase + WeasyPrint
├── frontend/            React 18 + Vite + Tailwind
├── reference/           PRD, tech stack, app flow, structure, plan
└── README.md
```

See `reference/` for the full PRD, technology stack, and 14-day implementation plan.

---

## Quick start (local dev)

### Prerequisites

- Python 3.11+
- Node.js 20+
- Supabase project (URL + service key + anon key)
- Cohere API key
- NewsAPI.org key
- GNews API key

### 1. Clone & configure env

```bash
git clone <repo>
cd Portfolionarator

# Backend env
cp backend/.env.example backend/.env
# Edit backend/.env — fill in SUPABASE_URL, COHERE_API_KEY, etc.

# Frontend env
cp frontend/.env.example frontend/.env
# Edit frontend/.env — fill in VITE_SUPABASE_URL, VITE_API_URL, etc.
```

### 2. Download fonts (one-time, manual)

WeasyPrint and the frontend both rely on locally-hosted fonts. Google Fonts CDN
fails inside WeasyPrint, so the .ttf / .woff2 files must live on disk.

Download from Google Fonts and place into the two folders:

| File                       | Destination (PDF)                       | Destination (Web)                  |
|----------------------------|-----------------------------------------|------------------------------------|
| `Inter-Regular.ttf/woff2`  | `backend/static/fonts/`                 | `frontend/public/fonts/`           |
| `Inter-Bold.ttf/woff2`     | `backend/static/fonts/`                 | `frontend/public/fonts/`           |
| `PlayfairDisplay-Bold.ttf` | `backend/static/fonts/`                 | `frontend/public/fonts/` (woff2)   |

### 3. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
# → http://localhost:8000/health  ⇒  {"status": "ok"}
# → http://localhost:8000/docs    ⇒  OpenAPI docs
```

### 4. Database (Supabase)

Run the SQL files in order:

```
backend/db_schema/schema.sql   # 10 tables
backend/db_schema/rls.sql      # Row-level security policies
backend/db_schema/seed.sql     # 5 synthetic HNI clients + portfolios + transactions
```

### 5. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

---

## Scheduling (EasyCron — production)

Once deployed, set up 4 HTTP jobs on EasyCron.com:

| Job              | URL                                                 | Schedule (IST)        |
|------------------|-----------------------------------------------------|-----------------------|
| Keep alive       | `GET /health`                                       | Every 10 minutes      |
| Daily news       | `GET /jobs/collect-daily-news?secret=$JOB_SECRET`   | Every day 7:00 PM     |
| Weekly summary   | `GET /jobs/weekly-summarise?secret=$JOB_SECRET`     | Sunday 11:00 PM       |
| Monthly reports  | `GET /jobs/generate-monthly?secret=$JOB_SECRET`     | Last day 6:00 AM      |

---

## Current build status

Day 1–2 scaffolding complete, Day 3 in progress:

- [x] Project structure (backend + frontend)
- [x] FastAPI app with CORS + /health
- [x] Pydantic models + utilities
- [x] Supabase SQL schema, RLS, seed data
- [x] PDF Jinja2 template
- [x] React app with Tailwind + routing skeleton
- [x] Supabase DB layer (clients, portfolios, transactions, price cache, news)
- [x] **Config tab**: live-edit agent .md files, RSS/NewsAPI/GNews feeds, style samples
- [ ] Market data fetcher (yfinance + cache fallback)
- [ ] News fetch implementations (feedparser / requests / GNews HTTP)
- [ ] Context builder
- [ ] Prompt builder final (Day 5 hand-written few-shots)
- [ ] Cohere streaming report generator
- [ ] PDF exporter (WeasyPrint wiring)

Hindi translation is **deferred** — English-only output for now.

### Config tab (new)

Once logged in, the **Config** tab in the top bar exposes:

- **Agents & instructions** — markdown files under `backend/config/agents/`
  (e.g. `HOUSE_VIEW.md`, `AGENTS.md`). Their content is concatenated and
  injected as system context on every generation via
  `prompt_builder.load_system_context()`.
- **Style samples** — paste or upload previous RM letters (saved into
  `backend/config/style_samples/`). Each one is added to the prompt as a
  few-shot example so the generator mimics the writer's voice.
- **News feeds** — RSS URLs, NewsAPI queries, GNews sectors stored in
  `backend/config/feeds.json` and read by `news_fetcher` at fetch time.

Edits take effect on the next request — no restart required.

---

## Documentation

| File                                  | Description                                  |
|---------------------------------------|----------------------------------------------|
| `reference/PRD.md`                    | Product requirements                         |
| `reference/TECH_STACK.md`             | Stack choices and rationale                  |
| `reference/APP_FLOW.md`               | User, data, news, admin flows                |
| `reference/FRONTEND_GUIDELINES.md`    | React structure + design system              |
| `reference/BACKEND_STRUCTURE.md`      | FastAPI structure + service contracts        |
| `reference/IMPLEMENTATION_PLAN.md`    | 14-day sprint plan                           |
