# PortfolioNarrator — Implementation Plan
**Version:** 2.0 | **Date:** May 2026
**Team:** You (AI + Full-stack) · Dev 2 (Backend + DB) · Dev 3 (Frontend + UI)
**Goal:** Live demo-ready app in 14 days

> **Build status (May 2026):** all code-level deliverables for Days 1–14
> are landed on `main`. The remaining work is operational only —
> creating the EasyCron jobs, deploying to Render + Vercel, running the
> live demo rehearsal, and exporting the pitch deck. See the per-day
> sections below for the granular checklist.

---

## What Changed in v2.0

| Area | v1.0 | v2.0 (Updated) |
|---|---|---|
| LLM | Claude API | Cohere Command R+ ($2,500 credits) |
| Scheduler | APScheduler (in-memory, dies on restart) | EasyCron.com (HTTP cron, survives restarts) |
| UptimeRobot | Required | Replaced with EasyCron keep-alive job |
| PDF fonts | Google CDN (breaks WeasyPrint) | Locally downloaded .ttf files |
| News fetching | Generic pre-collection | Portfolio-aware per-client at report time |
| Supabase schema | 8 tables | 10 tables (+ transactions, extended client fields) |
| JSON parsing | Direct json.loads (crashes) | safe_parse_json() with fallback |
| yfinance | No fallback | Supabase price_cache fallback |
| Hindi | Single-call translation | Two-step: English first → formal Hindi |
| CORS | Not specified | CORSMiddleware on Day 1 before any route |
| Client data | Basic profile only | Full PMS data model (6 categories) |
| Letter quality | Single LLM call | Two-call pipeline: generate → QA → regenerate if < 7 |
| Streaming | Polling / useState | Native fetch + ReadableStream |

---

## Pre-Start Checklist (Complete Before Day 1)

Do every single item here before writing one line of code.
A missing account on Day 3 will block the whole team.

**Accounts to create:**
- [ ] GitHub repo: `portfolionarrator` with `/frontend` and `/backend` folders
- [ ] Supabase — create project, note: URL, anon key, service key
- [ ] Cohere — generate production API key (confirm $2,500 credits loaded)
- [ ] NewsAPI.org — regenerate key (old one was exposed in chat)
- [ ] GNews.io — regenerate key (old one was exposed in chat)
- [ ] EasyCron.com — confirm account active, note API key safely
- [ ] Render.com — connect to GitHub repo
- [ ] Vercel — connect to GitHub repo

**Files to prepare locally:**
- [ ] Download `Inter-Regular.ttf` from Google Fonts → `backend/static/fonts/`
- [ ] Download `Inter-Bold.ttf` from Google Fonts → `backend/static/fonts/`
- [ ] Download `PlayfairDisplay-Bold.ttf` from Google Fonts → `backend/static/fonts/`
- [ ] Create `backend/.env` with all keys (see template below)
- [ ] Create `frontend/.env` with Supabase anon key + backend URL
- [ ] Add `.env` to `.gitignore` — do this before first commit

**`.env` template for backend:**
```
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
COHERE_API_KEY=
NEWSAPI_KEY=
GNEWS_API_KEY=
JOB_SECRET=<random 32-char string>
ADMIN_SECRET=<random 32-char string>
FRONTEND_URL=http://localhost:5173
```

**Security check:**
- [ ] Confirm no API keys are in any chat, email, or document
- [ ] Confirm `.gitignore` has `.env` before first `git push`
- [ ] Share keys only via password manager or encrypted channel

---

## Week 1 — Foundation & Core Engine (Days 1–7)

---

### Day 1 — Project Setup + CORS + DB Schema

**You:**
- [ ] Create FastAPI project structure exactly as per `BACKEND_STRUCTURE.md`
- [ ] Install: `fastapi`, `uvicorn`, `pydantic`, `python-dotenv`, `cohere`, `supabase`
- [ ] Create `main.py` with CORSMiddleware — this is the FIRST thing in the file before any routes:
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["http://localhost:5173", os.getenv("FRONTEND_URL")],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- [ ] Add `GET /health` endpoint — returns `{"status": "ok"}`
- [ ] Create `requirements.txt` with pinned versions
- [ ] Create `render.yaml` with WeasyPrint system dependencies:
  ```yaml
  buildCommand: |
    apt-get install -y libpango-1.0-0 libpangocairo-1.0-0
    libcairo2 libffi-dev shared-mime-info &&
    pip install -r requirements.txt
  ```
- [ ] Test: `uvicorn main:app --reload` starts without errors
- [ ] Test: `GET /health` returns 200
- [ ] Push to GitHub

**Dev 2:**
- [ ] Create Supabase project
- [ ] Run complete SQL schema — all 10 tables:

```sql
-- 1. Relationship Managers
create table rms (
    id          uuid primary key default gen_random_uuid(),
    email       text unique not null,
    name        text not null,
    firm_name   text,
    designation text default 'Relationship Manager',
    phone       text,
    created_at  timestamptz default now()
);

-- 2. HNI Clients (full PMS data model)
create table clients (
    id                   uuid primary key default gen_random_uuid(),
    rm_id                uuid references rms(id),
    -- Personal
    name                 text not null,
    pan_last4            text,
    dob                  date,
    client_since         date,
    -- Financial profile
    aum_cr               numeric(10,2),
    risk_profile         text,        -- conservative/moderate/aggressive
    investment_horizon   text,        -- 3yr/5yr/long_term
    liquidity_need_pct   numeric(5,2),
    income_need_monthly  numeric(10,2),
    tax_bracket          text,        -- 30%/HUF/NRI
    -- Communication
    language_pref        text default 'english',
    tone_pref            text default 'warm',
    -- Relationship
    next_review_date     date,
    last_meeting_date    date,
    last_meeting_notes   text,
    referral_source      text,
    rm_phone             text,
    rm_email             text,
    created_at           timestamptz default now()
);

-- 3. Portfolio Holdings
create table portfolios (
    id                   uuid primary key default gen_random_uuid(),
    client_id            uuid references clients(id),
    holdings             jsonb not null,
    -- holdings format:
    -- [{ "ticker": "TCS", "company_name": "Tata Consultancy Services",
    --    "isin": "INE467B01029", "qty": 50, "buy_price": 3200,
    --    "sector": "IT", "asset_class": "equity",
    --    "buy_date": "2025-01-15" }]
    benchmark            text default 'NIFTY50',
    inception_date       date,
    inception_return     numeric(8,4),
    xirr                 numeric(8,4),
    sharpe_ratio         numeric(6,4),
    max_drawdown         numeric(8,4),
    fees_this_quarter    numeric(12,2),
    fees_since_inception numeric(12,2),
    updated_at           timestamptz default now()
);

-- 4. Transaction History
create table transactions (
    id          uuid primary key default gen_random_uuid(),
    client_id   uuid references clients(id),
    txn_type    text,       -- buy/sell/dividend/bonus/rights
    ticker      text,
    isin        text,
    quantity    numeric,
    price       numeric(12,2),
    total_value numeric(14,2),
    txn_date    date,
    rationale   text,       -- RM's note: why this trade was made
    executed_by text,
    created_at  timestamptz default now()
);

-- 5. Daily News Headlines
create table daily_news (
    id          uuid primary key default gen_random_uuid(),
    date        date not null,
    category    text not null,
    headline    text not null,
    summary     text,
    source      text,
    created_at  timestamptz default now()
);
create index idx_daily_news_date on daily_news(date);

-- 6. Weekly AI Summaries
create table weekly_summaries (
    id          uuid primary key default gen_random_uuid(),
    week_start  date not null,
    week_end    date not null,
    summaries   jsonb not null,
    created_at  timestamptz default now()
);

-- 7. Generated Reports
create table reports (
    id              uuid primary key default gen_random_uuid(),
    client_id       uuid references clients(id),
    month           text not null,
    generated_text  text,
    hindi_text      text,
    qa_score        integer,
    pdf_url         text,
    created_at      timestamptz default now()
);
create index idx_reports_client_id on reports(client_id);

-- 8. Price Cache (yfinance fallback)
create table price_cache (
    ticker      text primary key,
    price       numeric(12,2),
    change_pct  numeric(8,4),
    fetched_at  timestamptz default now()
);

-- 9. Error Logs
create table error_logs (
    id          uuid primary key default gen_random_uuid(),
    job         text not null,
    error       text not null,
    context     jsonb default '{}',
    timestamp   timestamptz default now()
);

-- 10. Admin job run log
create table job_runs (
    id          uuid primary key default gen_random_uuid(),
    job_name    text not null,
    status      text,       -- success/error
    records     integer,    -- how many rows processed
    duration_ms integer,
    run_at      timestamptz default now()
);
```

- [ ] Enable RLS on `clients`, `portfolios`, `transactions`, `reports`
- [ ] Create RLS policies: RMs see only their own data
- [ ] Test: connect from Python with `supabase-py` — insert one row, read it back
- [ ] Create `db/supabase_client.py` — singleton client

**Dev 3:**
- [ ] Create React project: `npm create vite@latest frontend -- --template react`
- [ ] Install: `tailwindcss`, `react-router-dom`, `recharts`, `lucide-react`, `react-hot-toast`
- [ ] Configure Tailwind with design system colors from `FRONTEND_GUIDELINES.md`
- [ ] Copy font files to `frontend/public/fonts/` (Inter + Playfair Display)
- [ ] Add `@font-face` rules in `index.css` pointing to `/fonts/` (not CDN)
- [ ] Create full folder structure as per `FRONTEND_GUIDELINES.md`
- [ ] Create `services/supabase.js` — Supabase client init with anon key
- [ ] Create `services/api.js` — all functions stubbed (no implementation yet)
- [ ] Test: `npm run dev` runs, Tailwind applies correctly

**End of Day 1 check:**
- FastAPI `/health` returns 200 ✅
- Supabase has all 10 tables ✅
- React dev server runs with Tailwind ✅
- CORS middleware is first thing in `main.py` ✅

---

### Day 2 — Models + Utilities + Synthetic Data + PDF Template

**You:**
- [ ] Create `models/client.py`:
  ```python
  class HoldingItem(BaseModel):
      ticker: str
      company_name: str
      isin: str
      qty: float
      buy_price: float
      sector: str
      asset_class: str
      buy_date: date
      # Added at runtime by market_data service:
      current_price: float | None = None
      change_pct: float | None = None
      source: str = "live"  # live/cached/unavailable

  class ClientResponse(BaseModel):
      id: str
      name: str
      aum_cr: float
      risk_profile: str
      language_pref: str
      tone_pref: str
      investment_horizon: str | None
      client_since: date | None
      next_review_date: date | None
      last_meeting_notes: str | None
      rm_name: str
      rm_email: str | None
      rm_phone: str | None
  ```
- [ ] Create `models/report.py`:
  ```python
  class GenerateReportRequest(BaseModel):
      client_id: str
      month: str  # "2026-04"

  class ReportResponse(BaseModel):
      id: str
      client_id: str
      month: str
      qa_score: int | None
      created_at: str
  ```
- [ ] Create `utils/validators.py` — `validate_context()` — checks all 4 required fields
- [ ] Create `utils/json_safe.py` — `safe_parse_json()` — strips markdown, regex for `{}`, fallback
- [ ] Create `utils/token_counter.py` — `estimate_tokens(text)` — len(text)//4
- [ ] Create `utils/formatters.py` — INR, %, crore, month name formatters
- [ ] Create `services/error_logger.py` — `log_error()` with try/except wrapper
- [ ] Write unit tests for all utils — 5 tests each (30 min total)

**Dev 2:**
- [ ] Seed 5 synthetic HNI client profiles with FULL data model:

```sql
-- Step 1: create one RM
insert into rms (email, name, firm_name, designation, phone)
values ('priya@wealthfirm.com', 'Priya Sharma',
        'Kotak Private Banking', 'Senior Relationship Manager',
        '+91 98765 43210');

-- Step 2: create 5 clients (use the rm_id from above)
-- Rajesh Mehta — ₹2.5 Cr, IT+Banking, outperformer, English
insert into clients (rm_id, name, aum_cr, risk_profile,
    investment_horizon, liquidity_need_pct, tax_bracket,
    language_pref, tone_pref, client_since, next_review_date,
    last_meeting_notes, rm_email, rm_phone)
values (<rm_id>, 'Rajesh Mehta', 2.50, 'moderate',
    '5yr', 15.0, '30%', 'english', 'warm',
    '2023-04-01', '2026-05-15',
    'Client happy with IT allocation. Wants to explore gold.',
    'priya@wealthfirm.com', '+91 98765 43210');

-- Priya Iyer — ₹1.2 Cr, IT heavy, underperformer, formal
insert into clients (rm_id, name, aum_cr, risk_profile,
    investment_horizon, liquidity_need_pct, tax_bracket,
    language_pref, tone_pref, client_since, next_review_date,
    last_meeting_notes, rm_email, rm_phone)
values (<rm_id>, 'Priya Iyer', 1.20, 'aggressive',
    '3yr', 10.0, '30%', 'english', 'formal',
    '2024-01-15', '2026-06-01',
    'Concerned about IT underperformance. Discussed diversification.',
    'priya@wealthfirm.com', '+91 98765 43210');

-- Arjun Kapoor — ₹5 Cr, multi-asset, stable, warm
insert into clients (rm_id, name, aum_cr, risk_profile,
    investment_horizon, liquidity_need_pct, tax_bracket,
    language_pref, tone_pref, client_since, next_review_date,
    rm_email, rm_phone)
values (<rm_id>, 'Arjun Kapoor', 5.00, 'moderate',
    'long_term', 20.0, 'HUF', 'english', 'warm',
    '2022-07-01', '2026-05-20',
    'priya@wealthfirm.com', '+91 98765 43210');

-- Sunita Rao — ₹75L, conservative, HINDI, formal
insert into clients (rm_id, name, aum_cr, risk_profile,
    investment_horizon, liquidity_need_pct, income_need_monthly,
    tax_bracket, language_pref, tone_pref, client_since,
    rm_email, rm_phone)
values (<rm_id>, 'Sunita Rao', 0.75, 'conservative',
    '3yr', 30.0, 25000, '20%', 'hindi', 'formal',
    '2024-06-01',
    'priya@wealthfirm.com', '+91 98765 43210');

-- Vikram Shah — ₹8 Cr, UHNI, complex, concise
insert into clients (rm_id, name, aum_cr, risk_profile,
    investment_horizon, liquidity_need_pct, tax_bracket,
    language_pref, tone_pref, client_since, next_review_date,
    last_meeting_notes, rm_email, rm_phone)
values (<rm_id>, 'Vikram Shah', 8.00, 'aggressive',
    'long_term', 5.0, '30%', 'english', 'concise',
    '2021-01-01', '2026-05-25',
    'Interested in AIF exposure. Discussed US market risk.',
    'priya@wealthfirm.com', '+91 98765 43210');
```

- [ ] Seed realistic portfolio holdings for each client (actual NSE tickers with ISIN codes)
- [ ] Seed 3–5 recent transactions per client with `rationale` field filled in
- [ ] Create `db/clients_db.py` — `get_all_clients()`, `get_client()`, `get_portfolio()`, `get_transactions()`
- [ ] Create `routes/clients.py` — `GET /clients`, `GET /clients/{id}/portfolio`
- [ ] Test: `GET /clients` returns 5 clients with full profile

**Dev 3:**
- [ ] Build PDF HTML template `static/templates/letter_template.html`
- [ ] Use `file:///app/static/fonts/Inter-Regular.ttf` — NOT Google CDN
- [ ] Test WeasyPrint renders template to PDF with dummy text
- [ ] Verify fonts render correctly — no fallback to Arial/Times
- [ ] If fonts fail — use `FontConfiguration` object:
  ```python
  from weasyprint.text.fonts import FontConfiguration
  font_config = FontConfiguration()
  HTML(string=html).write_pdf(stylesheets=[css], font_config=font_config)
  ```
- [ ] Document fix in team chat

**End of Day 2 check:**
- `GET /clients` returns 5 full client profiles ✅
- All utils tested and working ✅
- PDF renders with correct fonts ✅

---

### Day 3 — Market Data + News Fetcher + Login + Dashboard

**You:**
- [ ] Create `services/market_data.py`:
  - `fetch_stock_price_safe(ticker)` — yfinance → price_cache fallback
  - `fetch_nifty_return(period)` — Nifty 50 return %
  - `fetch_macro_data()` — USD/INR + crude oil change
  - `compute_portfolio_return(holdings, prices)` — weighted average
  - `get_top_performers(holdings, n=3)` — sorted by return desc
  - `get_underperformers(holdings, n=3)` — sorted by return asc
- [ ] Create `db/cache_db.py` — `get_cached_price()`, `save_price_cache()`
- [ ] Test: fetch prices for TCS, INFY, HDFCBANK, RELIANCE
- [ ] Test: disconnect internet → price_cache fallback → returns cached with source="cached"
- [ ] Update `GET /clients/{id}/portfolio` to return live prices + computed returns
- [ ] Add stale price flag to response: `has_stale_prices: bool`, `stale_tickers: list`

**Dev 2:**
- [ ] Create `services/news_fetcher.py`:
  - `fetch_rss(url, limit)` — feedparser
  - `fetch_newsapi(query, limit)` — NewsAPI.org
  - `fetch_gnews(sector, limit)` — GNews API
  - `fetch_client_relevant_news(client_id, portfolio)` — portfolio-aware
- [ ] Test each source individually — verify headlines return correctly
- [ ] Create `db/news_db.py` — `save_daily_news()`, `get_recent_weekly_summaries(weeks=4)`
- [ ] Create `routes/jobs.py` with `GET /jobs/collect-daily-news`:
  - Validates `JOB_SECRET` query param
  - Runs news collection
  - Logs to `job_runs` table on success
  - Logs to `error_logs` on failure
- [ ] Test: hit endpoint manually → verify rows in `daily_news` table

**Dev 3:**
- [ ] Build `pages/Login.jsx`:
  - Email + password fields
  - Supabase Auth sign-in
  - Redirect to `/dashboard` on success
  - Error toast on wrong credentials
- [ ] Build `hooks/useAuth.js` — login, logout, session, protected route
- [ ] Add `ProtectedRoute` component — redirects to login if no session
- [ ] Build `pages/Dashboard.jsx`:
  - Fetch clients from `GET /clients`
  - Render `ClientCard` components in a grid
  - Search bar filters by client name
- [ ] Build `components/client/ClientCard.jsx`:
  - Name, AUM (₹X.XX Cr format), risk profile badge
  - Language badge (EN/HI), last report date
  - Hover effect → click navigates to `/clients/{id}`

**End of Day 3 check:**
- Login works, redirects to dashboard ✅
- Dashboard shows 5 client cards with live AUM ✅
- Portfolio returns computed with yfinance ✅
- News collection saves headlines to Supabase ✅

---

### Day 4 — Context Builder + EasyCron Setup + Client Detail Screen

**You:**
- [ ] Create `services/context_builder.py` — `build_context_packet(client_id, month)`:
  1. Fetch client + portfolio + transactions from Supabase
  2. Fetch live prices via `fetch_stock_price_safe()` for each holding
  3. Fetch Nifty return + macro data via yfinance
  4. Fetch portfolio-aware news via `fetch_client_relevant_news()`
  5. Fetch last 4 weekly summaries from Supabase
  6. Compute: return, alpha, top performers, underperformers
  7. Pull recent transaction rationale (last 3 trades with RM notes)
  8. Run `validate_context()` — raise ValueError if invalid
  9. Return complete context dict
- [ ] Test context packet for all 5 clients — inspect output manually
- [ ] Verify Rajesh and Priya produce meaningfully different context packets
- [ ] Add `estimate_tokens(context_string)` check — trim news if > 90,000 tokens
- [ ] Create `routes/admin.py`:
  - `GET /admin/health` — Supabase ping
  - `GET /admin/errors` — last 20 error_logs (requires ADMIN_SECRET)
  - `POST /admin/trigger-news-collection` (requires ADMIN_SECRET)

**Dev 2:**
- [ ] Set up EasyCron.com — add 4 jobs:

  | Job | URL | Schedule (IST) |
  |---|---|---|
  | Keep alive | `GET /health` | Every 10 minutes |
  | Daily news | `GET /jobs/collect-daily-news?secret=...` | Every day 7:00 PM |
  | Weekly summary | `GET /jobs/weekly-summarise?secret=...` | Sunday 11:00 PM |
  | Monthly reports | `GET /jobs/generate-monthly?secret=...` | Last day 6:00 AM |

- [ ] Test keep-alive job fires → Render stays warm
- [ ] Create `services/summariser.py` — `weekly_summarisation()`:
  - Fetch last 7 days from `daily_news`
  - Group by category
  - Cohere Command R call per category (cheaper model)
  - Save to `weekly_summaries` table
  - Log to `job_runs`
- [ ] Add `GET /jobs/weekly-summarise` endpoint
- [ ] Manually trigger → verify summary appears in Supabase

**Dev 3:**
- [ ] Build `pages/ClientDetail.jsx`:
  - Client info card: name, AUM, risk, RM name, client since
  - `has_stale_prices` → show `Banner` component in yellow
  - Month selector dropdown (last 6 months)
  - Generate Report button (disabled until month selected)
- [ ] Build `components/client/HoldingsTable.jsx`:
  - Columns: Stock | Sector | Qty | Buy Price | Current Price | Return %
  - Return % coloured: green positive, red negative (with + / - prefix)
  - Stale price indicator per row if `source === "cached"`
- [ ] Build `components/client/ReturnSummary.jsx`:
  - Portfolio return vs Nifty 50
  - Alpha displayed: "+1.1% over benchmark"
  - Green/red colour based on alpha sign
- [ ] Build `components/ui/Banner.jsx` — yellow stale price warning

**End of Day 4 check:**
- Context packet assembles correctly for all 5 clients ✅
- EasyCron keep-alive job running every 10 minutes ✅
- Client detail screen shows portfolio with colours ✅
- Weekly summarisation works ✅

---

### Day 5 — Prompt Engineering (You — Most Important Day)

**You — spend the whole day on this:**
- [ ] Write 2 real example RM letters manually (45 min each):
  - **Letter A:** IT-heavy outperformer (beat Nifty by 1.5%, TCS up 8%)
  - **Letter B:** Pharma-heavy underperformer (below Nifty by 2%, regulatory headwind)
  - These become the few-shot examples in every prompt
  - Make them genuinely good — specific stock names, real reasons, warm tone
- [ ] Create `services/prompt_builder.py`:
  ```python
  FEW_SHOT_LETTER_A = """..."""  # Letter A written above
  FEW_SHOT_LETTER_B = """..."""  # Letter B written above

  BANNED_PHRASES = [
      "market volatility", "challenging environment", "headwinds",
      "uncertain times", "it is worth noting", "needless to say",
      "going forward", "at this juncture", "in this regard",
  ]

  def build_prompt_safe(context: dict, strict: bool = False) -> str:
      banned_str = "\n".join(f"- '{p}'" for p in BANNED_PHRASES)
      ...
  ```
- [ ] Inject transaction rationale into Section 3:
  - If RM noted "Added TCS on IT dip — strong deal pipeline"
  - Section 3 can say: "Your TCS position, added in January on the IT sector dip, has delivered 8.3% — the deal pipeline commentary from their Q3 results has played out well"
- [ ] Test prompt in Cohere Playground (not in code) — iterate 10 times
- [ ] Score each output mentally: does it feel like a real RM wrote it?
- [ ] Lock final prompt — write it to `prompt_builder.py` — no more changes after today

**Dev 2:**
- [ ] Create `db/reports_db.py` — `save_report()`, `get_report()`, `get_reports_for_client()`
- [ ] Add `GET /reports?client_id=...` endpoint
- [ ] Complete `services/pdf_exporter.py`:
  - Jinja2 renders `letter_template.html`
  - WeasyPrint with FontConfiguration + local fonts
  - Returns PDF bytes
- [ ] Test PDF for Rajesh Mehta with dummy letter text
- [ ] Verify PDF looks professional — correct fonts, margins, letterhead

**Dev 3:**
- [ ] Build `hooks/useStreamReport.js` — complete streaming implementation:
  ```javascript
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  while (true) {
      const { done, value } = await reader.read()
      if (done) break
      setReportText(prev => prev + decoder.decode(value, { stream: true }))
  }
  ```
- [ ] Build `components/report/ReportViewer.jsx`:
  - Renders letter text as it streams in
  - Blinking cursor while streaming
  - Section headers styled distinctly
  - Serif font (Playfair Display) for letter body
- [ ] Test streaming with a dummy FastAPI endpoint:
  ```python
  @app.get("/test-stream")
  async def test_stream():
      async def gen():
          for word in "Hello this is a streaming test".split():
              yield word + " "
              await asyncio.sleep(0.3)
      return StreamingResponse(gen(), media_type="text/plain")
  ```

**End of Day 5 check:**
- 2 real few-shot example letters written and locked ✅
- Prompt produces quality output in Cohere Playground ✅
- Streaming works in browser with dummy endpoint ✅
- PDF renders with professional formatting ✅

---

### Day 6 — Report Generation Endpoint + Full Pipeline + Rich HTML View

**You:**
- [ ] Create `services/report_generator.py` — full two-call pipeline:
  1. `validate_context()` → raise `ValueError` if invalid
  2. `build_prompt_safe(context)` → estimate tokens → trim if needed
  3. Cohere `chat_stream()` → `command-r-plus-08-2024` → stream tokens
  4. After stream completes → `run_qa_check(full_text)` → score 1–10
  5. If score < 7 → `regenerate_strict(context, note)` → replace text
  6. `save_report(client_id, month, text, score)`
  7. Append a JSON meta trailer (`[[META]]{...}[[END]]`) to the stream so
     the frontend learns `report_id` + `qa_score` without a second call.
- [ ] **NEW: Rich HTML report view (in addition to the plain-text PDF).**
  - `static/templates/letter_card.html` — visual report card mirroring
    the PortfolioNarrator AI design:
    * Header band with firm logo + RM name + month tag
    * Personalised greeting block
    * **Portfolio Snapshot** — 5 KPI cards (Portfolio Value ₹ Cr,
      Total Return %, Benchmark Return %, Alpha %, Risk Profile)
    * **Performance Overview** — Chart.js line chart of the last 90
      trading days (portfolio NAV proxy vs. Nifty 50)
    * **Asset Allocation** — Chart.js doughnut by sector
    * **Top Contributors / Top Detractors** — two side-by-side tables
      derived from `top_performers` / `underperformers`
    * **Market Context** — 4 cards (Indian Markets, Global Markets,
      Economy, Outlook) populated from `weekly_summaries` + `macro`
    * **What's Next?** — 3 recommendation cards parsed from the
      letter's forward-view paragraph + house view
    * RM signature + contact + small QR linking back to the SaaS
  - `services/html_renderer.py` — Jinja2 renders the card against the
    saved report row + a fresh `build_context_packet` call. Returns a
    single self-contained HTML string (Chart.js via CDN, inline JSON
    data), safe to email or embed in an `<iframe>`.
  - New endpoint `GET /reports/{id}/view-html` → returns
    `text/html; charset=utf-8`. Used by the frontend "View HTML report"
    button.
- [ ] ~~Create `services/translator.py` — Hindi two-step pipeline~~
  **(DEFERRED — English only for v1 per product decision.)**
- [ ] Create `routes/reports.py`:
  - `POST /reports/generate-stream` → StreamingResponse
  - `GET /reports?client_id=...` → list reports for client
  - `GET /reports/{id}` → fetch one
  - `GET /reports/{id}/export-pdf` → PDF download
  - `GET /reports/{id}/view-html` → rich HTML report card
- [ ] Test: hit generate endpoint for all 5 clients — verify streaming works
- [ ] Test: QA check fires after stream — score returned in meta trailer
- [ ] Test: score < 7 triggers regeneration (manually set threshold to 9 temporarily)
- [ ] Test: open `view-html` URL in browser — chart renders, numbers tally

**Dev 2:**
- [ ] Wire `GET /reports/{id}/export-pdf` to pdf_exporter
- [ ] Test PDF download from browser — file opens correctly
- [ ] Add `POST /admin/trigger-all-reports` endpoint
- [ ] Add EasyCron job: `GET /jobs/generate-monthly` endpoint

**Dev 3:**
- [ ] Wire Generate Report button → `POST /reports/generate-stream`
- [ ] Connect `useStreamReport` hook → strip `[[META]]…[[END]]` trailer
      and surface `report_id` + `qa_score` to the caller
- [ ] Add **"View HTML report"** button on `ReportPage.jsx` that opens
      `GET /reports/{id}/view-html` in a new tab
- [ ] Build Download PDF button:
  - Calls `GET /reports/{id}/export-pdf`
  - Triggers browser file download
- [ ] Build `components/report/QAScoreBadge.jsx`:
  - Shows score after generation (small badge)
  - Green if ≥ 8, yellow if 7, orange if < 7
- [ ] ~~`components/report/LanguageToggle.jsx`~~ **(DEFERRED with Hindi.)**

**End of Day 6 check:**
- Full flow: generate → stream → view (text + rich HTML) → download PDF ✅
- QA check fires and scores correctly ✅
- HTML report card renders with live charts + numbers ✅
- Hindi translation deferred — flag visible in code but no UI ⏸
- PDF downloads with professional layout ✅

---

### Day 7 — Integration Day (All 3)

Test the entire system together end to end.

**Morning (2 hours) — integration testing:**
- [ ] Login → Dashboard → Rajesh Mehta → Generate Report → View → Download PDF
- [ ] Repeat for all 5 clients — confirm 5 different reports
- [ ] Language toggle → Sunita Rao Hindi report → verify headers in Hindi
- [ ] Disconnect internet → portfolio loads with cached prices + yellow banner
- [ ] Trigger news collection via admin panel → verify in Supabase
- [ ] Trigger weekly summary via admin → verify in Supabase
- [ ] Check error log → should be empty if all went well

**Afternoon (2 hours) — deploy and verify:**
- [ ] Push backend to GitHub → Render auto-deploys
- [ ] Verify Render build installs WeasyPrint dependencies (check build logs)
- [ ] Push frontend to GitHub → Vercel auto-deploys
- [ ] Update backend `.env` on Render: set `FRONTEND_URL` to Vercel URL
- [ ] Test full flow on production URLs — not localhost
- [ ] Confirm EasyCron keep-alive is hitting production URL
- [ ] Confirm no CORS errors in browser console on production

**End of Day 7 check:**
- Full demo flow works on production URLs ✅
- All 5 clients generate quality reports ✅
- PDF downloads correctly on production ✅
- No CORS errors in browser console ✅
- EasyCron keep-alive confirmed working ✅

---

## Week 2 — Polish, Quality & Demo Readiness (Days 8–14)

---

### Day 8 — Prompt Quality Tuning (You) + Admin Panel (Dev 2) + UI Polish 1 (Dev 3)

**You:**
- [ ] Generate 20 reports across all 5 clients
- [ ] Read every single output — score each section 1–10 mentally
- [ ] Identify the 2 weakest sections (usually Section 3 and Section 5)
- [ ] Add more specificity to Section 3 prompt:
  - Inject `transaction_rationale` from recent trades
  - Force: "Reference the specific RM decision that led to this position"
- [ ] Add Hindi section header verification:
  - After translation, check all 7 headers are in Hindi
  - If any English header found → add a correction pass
- [ ] Target: avg QA score > 7.5 across 20 generated reports
- [ ] Test Vikram Shah (UHNI, complex portfolio) — 20+ holdings
  - Confirm token count stays under 90,000
  - Confirm context trimming kicks in correctly

**Dev 2:**
- [ ] Build `/admin` routes:
  - `POST /admin/trigger-news-collection`
  - `POST /admin/trigger-weekly-summary`
  - `POST /admin/trigger-all-reports`
  - `GET /admin/errors` — last 20 error_logs
  - `GET /admin/job-runs` — last 10 job_runs entries
- [ ] Add retry logic for Cohere API timeouts:
  ```python
  for attempt in range(3):
      try:
          response = co.chat_stream(...)
          break
      except cohere.error.CohereAPIError:
          if attempt == 2: raise
          await asyncio.sleep(2 ** attempt)
  ```
- [ ] Add request timeout: `timeout=45` on all Cohere calls

**Dev 3:**
- [ ] Build `pages/AdminPage.jsx`:
  - `components/admin/TriggerPanel.jsx` — 3 trigger buttons
  - `components/admin/ErrorLogTable.jsx` — last 20 errors
  - Job run history — last 10 runs with status
- [ ] UI polish pass 1:
  - Consistent spacing across all screens
  - Empty state: "No reports yet" for new client
  - Error state: friendly message for each API failure type
  - Return % numbers: green/red with arrow icons ↑ ↓

---

### Day 9 — Edge Cases + Streaming Robustness + UI Polish 2

**You:**
- [ ] Test all edge cases:
  - Client with 0 holdings → clear error message, not crash
  - Client with all unavailable prices → error before LLM call
  - Cohere timeout (set timeout=2 temporarily) → retry → user sees message
  - Very large portfolio (add 25 holdings to Vikram) → token trim works
  - Month with no weekly summaries → graceful fallback to RSS only
- [ ] Add input sanitisation:
  - Strip HTML from any text fields before injecting into prompt
  - Cap `last_meeting_notes` at 500 characters in prompt

**Dev 2:**
- [ ] Add stream interruption handling:
  ```python
  try:
      async for chunk in generate_report_stream(...):
          yield chunk
  except Exception as e:
      yield f"\n\n[Generation interrupted: {str(e)}]"
      await log_error("stream_interrupted", str(e))
  ```
- [ ] Test: close browser mid-stream → no unhandled exception on server
- [ ] Add `GET /reports/{id}` — fetch single report for re-viewing
- [ ] Test: navigate away from report → come back → report re-loads from Supabase

**Dev 3:**
- [ ] UI polish pass 2:
  - AUM in Indian format: `₹2.47 Cr` (not `₹2,470,000`)
  - All dates in Indian format: `15 April 2026`
  - Report section dividers — subtle horizontal line between sections
  - Smooth scroll to report top after generation completes
  - Mobile check — dashboard and client detail usable on phone
- [ ] Add past reports list to ClientDetail:
  - `GET /reports?client_id=...` → list with month + QA score
  - Click past report → navigate to `/clients/{id}/report/{report_id}`
  - Re-render from saved text (not re-generate)

---

### Day 10 — Full System Test (All 3)

Run the complete system as a real user would — no shortcuts.

**Morning — happy path testing:**
- [ ] 10 full report generations without any crashes
- [ ] 5 different clients → 5 clearly different reports (spot check Section 3)
- [ ] 3 Hindi reports → all section headers in Hindi, numbers in English
- [ ] 3 PDF downloads → open in Preview, Adobe, browser viewer
- [ ] Past report re-view → loads from Supabase, not re-generated
- [ ] Admin panel triggers → all 3 work, show in job_runs

**Afternoon — error path testing:**
- [ ] Wrong login → friendly error toast (not raw Supabase error)
- [ ] Generate with incomplete portfolio → clear error (not 500)
- [ ] Admin panel wrong secret → 403 with clear message
- [ ] yfinance unavailable → cached prices + yellow banner shown
- [ ] Cohere slow (add `time.sleep(50)` temporarily) → timeout → retry → user message
- [ ] Fix every bug found — document in GitHub Issues

---

### Day 11 — Security + Performance (All 3)

**You:**
- [ ] Security audit:
  - Confirm no API keys anywhere in code or git history
  - Confirm CORS only allows `localhost:5173` and Vercel URL — not `*`
  - Confirm `JOB_SECRET` validation on all job endpoints
  - Confirm `ADMIN_SECRET` validation on all admin endpoints
  - Confirm Supabase service key only in backend — never in frontend
- [ ] Add simple rate limiting:
  ```python
  from collections import defaultdict
  import time
  _rate_cache = defaultdict(list)
  def check_rate_limit(rm_id: str, limit: int = 10, window: int = 3600):
      now = time.time()
      _rate_cache[rm_id] = [t for t in _rate_cache[rm_id] if now - t < window]
      if len(_rate_cache[rm_id]) >= limit:
          raise HTTPException(429, "Too many report generations. Try later.")
      _rate_cache[rm_id].append(now)
  ```
- [ ] Add request logging middleware

**Dev 2:**
- [ ] Verify Supabase RLS: log in as RM A, confirm cannot see RM B's clients
- [ ] Check Supabase indexes exist on `daily_news.date` and `reports.client_id`
- [ ] Test PDF generation time — target < 10 seconds
- [ ] Confirm Render build logs show WeasyPrint dependencies installed

**Dev 3:**
- [ ] Lighthouse audit on Dashboard — fix performance issues
- [ ] Confirm every button has loading state for async actions
- [ ] Tab navigation order is logical on all screens
- [ ] Accessibility: all interactive elements have `aria-label`

---

### Day 12 — Demo Script + Rehearsal (All 3)

**Dev 3 — write demo script:**
```
00:00 — Open app on production URL — already loaded (warmed up 5 min ago)
00:15 — Log in as Priya Sharma (RM)
00:30 — Show dashboard — "5 HNI clients, managed by this RM"
01:00 — Open Rajesh Mehta — show portfolio: ₹2.5 Cr, beat Nifty by 1.1%
01:30 — "Let's generate the April 2026 quarterly review letter"
01:45 — Click Generate — watch letter stream live on screen
02:30 — Scroll to Section 3 — read it aloud: "This is why his portfolio
         beat Nifty — TCS up 8.3%, added in January on the IT sector dip"
03:00 — "Now Section 5 — we're honest about Paytm"
03:20 — Click Download PDF — open the file — show letterhead
03:40 — Switch to Sunita Rao — click Generate — click Hindi toggle
04:00 — Show Hindi letter — section headers in Hindi, numbers in English
04:20 — "In production this connects to the client's actual broker account"
04:30 — Show admin panel — trigger news collection live
05:00 — Q&A
```

**All 3 — rehearsal:**
- [ ] Rehearse demo twice — time it (must be under 5 minutes)
- [ ] Identify any slow spots or awkward transitions → fix them
- [ ] Prepare answer for: "How accurate are the numbers?"
- [ ] Prepare answer for: "What about data security / DPDP?"
- [ ] Prepare answer for: "Can it connect to our existing PMS system?"
- [ ] Prepare backup: screen recording of perfect demo run

---

### Day 13 — Pitch Deck + Documentation (Dev 2 + You) / Final UI (Dev 3)

**Dev 2 — 7-slide pitch deck:**
- [ ] Slide 1: The Problem — "200 clients × 12 hours = 2,400 hours every quarter"
- [ ] Slide 2: The Solution — PortfolioNarrator in one sentence + screenshot
- [ ] Slide 3: Demo screenshot — report viewer with streaming
- [ ] Slide 4: How it works — 4-step pipeline diagram (data → context → AI → PDF)
- [ ] Slide 5: ROI — "2,400 hrs → 3 hrs. Same quarter. Same quality. Better consistency."
- [ ] Slide 6: Pricing — ₹10L (50 clients) / ₹20L (200 clients) / ₹40L (500+ clients)
- [ ] Slide 7: Free pilot — "First 3 clients' April reports generated free. No commitment."
- [ ] Export PDF version

**You — README.md:**
- [ ] How to run locally (5 steps)
- [ ] Environment variables list
- [ ] How to seed synthetic data
- [ ] How to set up EasyCron jobs
- [ ] Known limitations

**Dev 3 — final UI:**
- [ ] Screenshot every screen — review for any visual inconsistencies
- [ ] Fix any last pixel-level issues
- [ ] Confirm firm logo placeholder looks intentional (not broken)

---

### Day 14 — Demo Day (All 3)

**Morning checklist (9am):**
- [ ] Production URL loads in < 2 seconds
- [ ] Generate one report each for all 5 clients — all succeed
- [ ] PDF downloads for all 5
- [ ] Hindi toggle works for Sunita Rao
- [ ] Admin panel shows no errors in error log
- [ ] EasyCron shows keep-alive fired in last 10 minutes
- [ ] Pitch deck opens correctly on demo device

**30 minutes before demo:**
- [ ] Open production URL — warm it up with a health check
- [ ] Generate Rajesh Mehta report — have it ready to show
- [ ] Close all other browser tabs
- [ ] Put phone on silent
- [ ] Have backup screen recording ready

**Demo Definition of Done:**
- [ ] ✅ 5 clients load on dashboard
- [ ] ✅ Report generates and streams in < 60 seconds
- [ ] ✅ Section 3 reads like a real RM wrote it — not a template
- [ ] ✅ PDF downloads with professional letterhead
- [ ] ✅ Hindi toggle works for Sunita Rao
- [ ] ✅ No crashes in 5-minute live walkthrough
- [ ] ✅ Every question answered confidently

---

## Post-Demo Roadmap

| Week | Feature | Owner | Notes |
|---|---|---|---|
| Week 3 | Angel One SmartAPI OAuth | You | Real portfolio connection |
| Week 3 | CSV portfolio upload | Dev 2 | Manual import for first client |
| Week 4 | RM editable sections before PDF | Dev 3 | Human-in-the-loop |
| Week 4 | First paid client onboarding | All | Target: independent MFD |
| Month 2 | Multi-RM login + client assignment | Dev 2 | For firms with multiple RMs |
| Month 2 | Supabase Storage for PDF archive | Dev 2 | Permanent report storage |
| Month 3 | WhatsApp delivery via Twilio | You | Direct to HNI client |
| Month 3 | Marathi / Tamil language support | You | Expand vernacular |
| Month 4 | Email dispatch post-RM-approval | Dev 2 | Full automation loop |
| Month 4 | SEBI audit trail export | Dev 2 | Compliance requirement |

---

## Daily Standup Format (10 minutes max)

Every morning at 10am:

```
Each person answers:
1. What did I complete yesterday?
2. What am I building today?
3. Any blockers? → resolve same day, not tomorrow
```

Rule: if blocked for more than 2 hours → ask team immediately.
No silent blocking — it kills the sprint.

---

## Critical Rules for the Sprint

1. **CORS middleware goes in `main.py` before any route — always**
2. **No API keys in code, chat, or commits — ever**
3. **Test on production URL every day from Day 7 — not just localhost**
4. **Prompt is locked after Day 5 — no changes in Week 2**
5. **PDF template is tested on Day 2 — not Day 13**
6. **EasyCron keep-alive runs from Day 4 — not Day 14**
7. **Every async button has a loading state — no exceptions**
