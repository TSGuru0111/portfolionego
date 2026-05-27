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
backend/db_schema/schema.sql                      # 10 base tables
backend/db_schema/rls.sql                         # Base row-level security policies
backend/db_schema/seed.sql                        # 5 synthetic HNI clients + portfolios + transactions
backend/db_schema/migrations/001_qa_reasons.sql   # adds qa_reasons JSONB to reports (additive)
backend/db_schema/migrations/002_multi_asset.sql  # Phase 1 — 10 multi-asset tables + RLS
backend/db_schema/seed_v2.sql                     # Phase 1 multi-asset rows for the same 5 clients
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

All core sprint days (1–14) are code-complete. The remaining work is
operational: EasyCron cron-job setup, Render/Vercel deployment, and the
live demo rehearsal.

- [x] Project structure (backend + frontend) — Day 1
- [x] FastAPI app with CORS + `/health` — Day 1
- [x] Pydantic models + utilities + unit tests — Day 2
- [x] Supabase SQL schema, RLS, seed data — Day 1–2
- [x] PDF Jinja2 template — Day 2
- [x] React app with Tailwind + routing skeleton — Day 1
- [x] Supabase DB layer (clients, portfolios, transactions, price cache, news) — Day 2–3
- [x] **Config tab**: live-edit agent `.md` files, RSS/NewsAPI/GNews feeds, style samples — Day 3
- [x] Market data fetcher (yfinance + cache fallback) — Day 3
- [x] News fetch implementations (RSS + NewsAPI + GNews) — Day 3
- [x] Context builder + input sanitisation (HTML strip, 500-char cap) — Day 4 + Day 9
- [x] Weekly news summariser (Cohere Command R) — Day 4
- [x] Prompt builder locked with 2 hand-written few-shot RM letters — Day 5
- [x] Reports CRUD + PDF exporter (lazy WeasyPrint) — Day 5
- [x] Cohere streaming report generator + QA + regen pipeline — Day 6
- [x] Rich HTML report card (Chart.js inline data, served at `/reports/{id}/view-html`) — Day 6
- [x] Admin: trigger-news, trigger-weekly, trigger-all-reports, error log, job-runs — Day 8
- [x] EasyCron job endpoints (collect-daily-news, weekly-summarise, generate-monthly) — Day 4 + Day 8
- [x] Cohere retry helper with exponential backoff — Day 8
- [x] Stream-error trailer + non-streamed `generate_report_batch` for cron — Day 9
- [x] Past-reports list on ClientDetail; re-view loads saved text from DB — Day 9
- [x] Rate limit (20/hr per IP on `/reports/generate-stream`) + request logging — Day 11

Hindi translation is **deferred** — English-only output for v1.

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

## Environment variables

### Backend (`backend/.env`)

```
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
COHERE_API_KEY=
NEWSAPI_KEY=
GNEWS_API_KEY=
JOB_SECRET=<random 32-char string>           # EasyCron auth
ADMIN_SECRET=<random 32-char string>         # Admin console auth
FIRM_NAME="Wealth Advisory Group"            # used in HTML letterhead
FRONTEND_URL=http://localhost:5173           # CORS allow-list entry
```

### Frontend (`frontend/.env`)

```
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
VITE_API_URL=http://localhost:8000
```

---

## Demo flow (5 minutes)

1. Open the production URL — already warm (EasyCron keep-alive ran 10 min ago).
2. Log in as the RM. Dashboard shows the 5 seeded HNI clients.
3. Open Rajesh Mehta — review portfolio (₹2.5 Cr, IT-heavy, beat Nifty).
4. Pick last month and click **Generate report** — letter streams live.
5. Open the **View HTML report** tab → rich card with KPIs, charts, market context.
6. Click **Download PDF** → file opens with the firm letterhead.
7. From client detail, open a past report — it loads from Supabase instantly.
8. Open `/admin` → trigger news collection live, then refresh the job-runs panel.

---

## Known limitations

- **Hindi translation deferred** — code paths exist but no UI surface; flagged
  for Phase 2 alongside Marathi and Tamil.
- **PDF rendering needs system libs** — WeasyPrint is lazy-imported and the
  `requirements.txt` line is commented; on Render the buildCommand installs
  `libpango`, `libcairo`, etc. Locally on macOS install via Homebrew first.
- **No real broker integration** — portfolio data is seeded into Supabase by
  hand. Angel One SmartAPI OAuth is on the Week-3 post-demo roadmap.
- **Rate limit is in-memory** — survives a single worker only; for a multi-
  worker Render plan, replace with a Redis-backed token bucket.
- **`_synth_perf_series`** — we do not store historical NAVs, so the 90-day
  HTML card chart is a deterministic walk anchored to real month-end returns.
  Once we add daily NAV snapshots, swap the synth for real series.
- **QA score 0** means Cohere was unreachable, not "bad letter" — the badge
  hides itself when the score is null.

---

## Multi-Asset Data Model (Phase 1)

Phase 1 ships the data + valuation layer for non-equity assets without touching
the LLM context. Reports remain equity-only until Phase 3.

- 10 new tables in `backend/db_schema/migrations/002_multi_asset.sql`:
  `mutual_funds`, `bonds`, `gold_holdings`, `cash_balances`, `fixed_deposits`,
  `insurance_policies`, `liabilities` (client-scoped) +
  `market_yields`, `nav_cache`, `gold_price_cache` (support).
- CRUD lives in `backend/db/{table}_db.py` — same singleton + `RuntimeError`
  convention as existing modules.
- Pure valuators in `backend/services/valuators/`:
  `fd_valuator`, `bond_pricer`, `insurance_valuator`, `liability_valuator`.
- Feeds in `backend/services/feeds/`: `amfi_nav` (NAVAll.txt parser),
  `gold_price` (IBJA scraper). Refreshed by two new cron endpoints
  `/jobs/refresh-nav-cache` and `/jobs/refresh-gold-price` (shared `JOB_SECRET`).
- Integration point: `services.wealth_aggregator.build_wealth_snapshot(client_id, as_of)`
  returns a `WealthSnapshot` (pydantic model in `models/wealth.py`). It is
  **not** called from `context_builder.py` in Phase 1 — wire-in is Phase 3.
- Seed: apply `seed.sql` first, then `seed_v2.sql` for multi-asset rows on the
  5 demo clients.

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
