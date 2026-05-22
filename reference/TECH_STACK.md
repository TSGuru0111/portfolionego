# PortfolioNarrator — Technology Stack
**Version:** 1.0 | **Date:** May 2026

---

## 1. Stack Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                             │
│          React 18 + Vite + Tailwind CSS                     │
│                    Vercel (Deploy)                           │
├─────────────────────────────────────────────────────────────┤
│                        BACKEND                              │
│              FastAPI (Python 3.11+)                         │
│                   Render (Deploy)                            │
├─────────────────────────────────────────────────────────────┤
│                       DATABASE                              │
│              Supabase (PostgreSQL 15)                        │
│           + Supabase Auth + Supabase RLS                     │
├─────────────────────────────────────────────────────────────┤
│                      AI / LLM                               │
│     Cohere Command R+ (report generation, QA, Hindi)        │
│     Cohere Command R  (news summarisation — cheaper)         │
├─────────────────────────────────────────────────────────────┤
│                    MARKET DATA                              │
│        yfinance (NSE/BSE live prices, Nifty return)         │
│              + Supabase price_cache (fallback)               │
├─────────────────────────────────────────────────────────────┤
│                      NEWS DATA                              │
│   feedparser (Moneycontrol RSS, ET RSS, RBI RSS, NSE RSS)   │
│        NewsAPI.org (stock-specific — 100 req/day free)       │
│           GNews API (sector news — 100 req/day free)         │
├─────────────────────────────────────────────────────────────┤
│                  PDF GENERATION                             │
│         WeasyPrint + Jinja2 + locally-hosted fonts          │
├─────────────────────────────────────────────────────────────┤
│                    SCHEDULING                               │
│    EasyCron.com (HTTP cron — survives Render restarts)       │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Frontend

### 2.1 Core

| Technology | Version | Purpose |
|---|---|---|
| React | 18.x | UI framework |
| Vite | 5.x | Build tool (fast dev server) |
| React Router | 6.x | Client-side routing |
| Tailwind CSS | 3.x | Utility-first styling |

### 2.2 Data Fetching

| Technology | Purpose |
|---|---|
| Native fetch() API | All API calls to FastAPI backend |
| ReadableStream + fetch | Streaming report generation |
| Supabase JS Client | Auth + direct DB reads for simple queries |

### 2.3 UI Components

| Technology | Purpose |
|---|---|
| Recharts | Portfolio donut chart, return bar chart |
| Lucide React | Icons throughout |
| React Hot Toast | Success/error notifications |

### 2.4 Why These Choices

- **Vite over CRA:** Significantly faster dev server startup and HMR
- **Tailwind over CSS-in-JS:** Faster to build, easier for Dev 3 with design background
- **Native fetch over Axios:** Streaming support required — Axios handles streaming poorly
- **Recharts over Chart.js:** Better React integration, easier theming

---

## 3. Backend

### 3.1 Core

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Runtime |
| FastAPI | 0.111+ | API framework |
| Uvicorn | 0.29+ | ASGI server |
| Pydantic | 2.x | Request/response validation |

### 3.2 Key Libraries

| Library | Purpose |
|---|---|
| cohere | Cohere Command R+ API client |
| yfinance | NSE/BSE live market data |
| feedparser | RSS feed parsing (news) |
| requests | NewsAPI + GNews HTTP calls |
| supabase-py | Supabase database client |
| WeasyPrint | HTML → PDF generation |
| Jinja2 | PDF HTML template rendering |
| python-dotenv | Environment variable management |
| APScheduler | NOT USED — replaced by EasyCron |

### 3.3 Why FastAPI over Flask/Django

- Native async support — critical for parallel news fetching and streaming
- Auto-generated OpenAPI docs (useful for team API reference)
- Pydantic validation built in — prevents malformed data reaching LLM
- StreamingResponse native support — needed for Cohere streaming

### 3.4 Why NOT APScheduler

APScheduler stores jobs in memory. Every Render deployment or restart kills all scheduled jobs silently. This would cause daily news collection to stop working without any visible error. EasyCron.com makes HTTP calls to FastAPI endpoints on a schedule — jobs survive restarts, and failures are visible in EasyCron logs.

---

## 4. Database — Supabase

### 4.1 Schema

```sql
-- Relationship Managers
create table rms (
    id          uuid primary key default gen_random_uuid(),
    email       text unique not null,
    name        text not null,
    firm_name   text,
    designation text default 'Relationship Manager',
    phone       text,
    created_at  timestamptz default now()
);

-- HNI Clients
create table clients (
    id              uuid primary key default gen_random_uuid(),
    rm_id           uuid references rms(id),
    name            text not null,
    aum_cr          numeric(10,2),       -- AUM in crores
    risk_profile    text,                -- conservative/moderate/aggressive
    language_pref   text default 'english',
    tone_pref       text default 'warm', -- warm/formal/concise
    firm_name       text,
    created_at      timestamptz default now()
);

-- Portfolio Holdings
create table portfolios (
    id          uuid primary key default gen_random_uuid(),
    client_id   uuid references clients(id),
    holdings    jsonb not null,
    -- holdings format:
    -- [{ "ticker": "TCS", "qty": 50, "buy_price": 3200,
    --    "sector": "IT", "asset_class": "equity" }]
    benchmark   text default 'NIFTY50',
    updated_at  timestamptz default now()
);

-- Daily News Headlines
create table daily_news (
    id          uuid primary key default gen_random_uuid(),
    date        date not null,
    category    text not null,
    -- market | regulatory | sector_IT | sector_BFSI |
    -- sector_Pharma | sector_FMCG | global
    headline    text not null,
    summary     text,
    source      text,
    created_at  timestamptz default now()
);

-- Weekly AI Summaries
create table weekly_summaries (
    id          uuid primary key default gen_random_uuid(),
    week_start  date not null,
    week_end    date not null,
    summaries   jsonb not null,
    -- { "market": "...", "regulatory": "...",
    --   "sector_IT": "...", "global": "..." }
    created_at  timestamptz default now()
);

-- Generated Reports
create table reports (
    id              uuid primary key default gen_random_uuid(),
    client_id       uuid references clients(id),
    month           text not null,  -- "2026-04"
    generated_text  text,           -- English version
    hindi_text      text,           -- Hindi version (nullable)
    qa_score        integer,        -- 1-10 from QA checker
    pdf_url         text,           -- Supabase storage URL (future)
    created_at      timestamptz default now()
);

-- Price Cache (yfinance fallback)
create table price_cache (
    ticker      text primary key,
    price       numeric(12,2),
    change_pct  numeric(8,4),
    fetched_at  timestamptz default now()
);

-- Error Logs
create table error_logs (
    id          uuid primary key default gen_random_uuid(),
    job         text not null,
    error       text not null,
    context     jsonb default '{}',
    timestamp   timestamptz default now()
);
```

### 4.2 Row Level Security (RLS)

```sql
-- RMs can only see their own clients
alter table clients enable row level security;
create policy "RMs see own clients" on clients
    for all using (rm_id = auth.uid());

-- Reports visible only to the RM who owns the client
alter table reports enable row level security;
create policy "RMs see own reports" on reports
    for all using (
        client_id in (
            select id from clients where rm_id = auth.uid()
        )
    );

-- News and summaries are public read (no PII)
alter table daily_news enable row level security;
create policy "Public read news" on daily_news
    for select using (true);
```

### 4.3 Why Supabase

- Free tier includes Auth, DB, RLS, and storage — everything needed in one service
- Supabase-py client works seamlessly with FastAPI async
- Built-in RLS prevents one RM from accessing another's clients — zero code
- Real-time subscriptions available for future WebSocket features

---

## 5. AI / LLM — Cohere

### 5.1 Model Assignment

| Task | Model | Reason |
|---|---|---|
| Report generation | `command-r-plus-08-2024` | Highest quality writing |
| QA scoring | `command-r-plus-08-2024` | Needs judgment ability |
| Hindi translation | `command-r-plus-08-2024` | Best multilingual in Cohere |
| News summarisation | `command-r-08-2024` | Cheaper, sufficient quality |

### 5.2 Cost Estimate

| Task | Tokens (in/out) | Cost per call | Monthly (200 clients) |
|---|---|---|---|
| Report generation | 3,000 / 1,500 | $0.0225 | $4.50 |
| QA check | 2,000 / 200 | $0.007 | $1.40 |
| Hindi translation | 2,500 / 2,000 | $0.026 | $5.20 (if all need Hindi) |
| Weekly summarisation | 1,000 / 300 | $0.005 | $0.08 (4 calls/month) |
| **Total/month** | | | **~$11** |

$2,500 budget → **~227 months of operation.** Effectively unlimited for demo.

### 5.3 Prompt Strategy

- **System/preamble:** Senior RM persona with 12 years experience
- **Few-shot:** 2 real example RM letters included in every prompt
- **Negative instructions:** Explicit list of banned generic phrases
- **Structural enforcement:** Numbered 7-section format required
- **Data grounding:** "Use ONLY the data provided. Do NOT invent numbers."
- **Length control:** Each section specified in word count

---

## 6. Market Data — yfinance

### 6.1 Data Fetched

| Data Point | yfinance Call | Fallback |
|---|---|---|
| Individual stock price | `Ticker("TCS.NS").history("2d")` | Supabase price_cache |
| Nifty 50 return | `Ticker("^NSEI").history("1mo")` | Hardcoded last known |
| USD/INR change | `Ticker("INR=X").history("1mo")` | Skip (optional) |
| Crude oil change | `Ticker("CL=F").history("1mo")` | Skip (optional) |

### 6.2 Why yfinance (Not Broker API)

For demo: yfinance requires zero registration, zero OAuth, zero client broker account. The first client who signs up will integrate their own broker (Angel One SmartAPI — free) post-demo.

### 6.3 Price Cache Strategy

Every successful fetch updates Supabase `price_cache`. On failure, last cached value is used with timestamp. Frontend shows yellow banner when cache is used — transparency for RM.

---

## 7. News Data Sources

| Source | Type | Free Limit | Category |
|---|---|---|---|
| Moneycontrol RSS | RSS | Unlimited | market |
| Economic Times RSS | RSS | Unlimited | market |
| RBI Press Release RSS | RSS | Unlimited | regulatory |
| NSE Corporate Actions RSS | RSS | Unlimited | regulatory |
| NewsAPI.org | REST API | 100 req/day | stock-specific |
| GNews API | REST API | 100 req/day | sector |

**100 req/day is sufficient:** Daily collection makes ~10 NewsAPI calls and ~8 GNews calls. Well within limits.

---

## 8. PDF Generation — WeasyPrint

### 8.1 Dependencies (must install on Render)

```bash
# render.yaml build command
apt-get install -y \
  libpango-1.0-0 \
  libpangocairo-1.0-0 \
  libcairo2 \
  libffi-dev \
  shared-mime-info
```

### 8.2 Font Strategy

Google Fonts CDN fails with WeasyPrint. Fonts are downloaded locally to `backend/static/fonts/`:
- `Inter-Regular.ttf`
- `Inter-Bold.ttf`
- `PlayfairDisplay-Bold.ttf`

Referenced via `file://` URL in CSS — not via CDN.

### 8.3 Template Engine

Jinja2 renders the HTML letter template with client and report data before passing to WeasyPrint. Variables: `client_name`, `rm_name`, `firm_name`, `month`, `letter_body`.

---

## 9. Scheduling — EasyCron

| Job | Schedule (IST) | Endpoint |
|---|---|---|
| Daily news collection | Every day 7:00 PM | `GET /jobs/collect-daily-news` |
| Weekly summarisation | Sunday 11:00 PM | `GET /jobs/weekly-summarise` |
| Monthly report generation | Last day of month 6:00 AM | `GET /jobs/generate-monthly` |

All endpoints protected with `JOB_SECRET` query parameter from environment.

---

## 10. Deployment

| Component | Platform | Plan | Cost |
|---|---|---|---|
| Frontend | Vercel | Free (Hobby) | ₹0 |
| Backend | Render | Free (Web Service) | ₹0 |
| Database | Supabase | Free tier | ₹0 |
| Domain (optional) | Namecheap | — | ~₹800/year |
| UptimeRobot | UptimeRobot | Free | ₹0 |
| EasyCron | EasyCron.com | Free (20 jobs) | ₹0 |
| Cohere | Cohere API | $2,500 credits | ~$11/month |

**Total infrastructure cost during demo: ₹0**

### 10.1 Render Spin-Down Prevention

Render free tier sleeps after 15 minutes of inactivity. Solution:
- UptimeRobot pings `GET /health` every 10 minutes
- `/health` endpoint just returns `{"status": "ok"}` — no DB hit

### 10.2 Environment Variables

```bash
# Backend (.env)
SUPABASE_URL=
SUPABASE_SERVICE_KEY=         # Service key (not anon — needed for server-side)
COHERE_API_KEY=
NEWSAPI_KEY=
GNEWS_API_KEY=
JOB_SECRET=                   # Random string for EasyCron endpoint auth
ADMIN_SECRET=                 # Random string for admin panel auth
FRONTEND_URL=                 # Vercel URL for CORS

# Frontend (.env)
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=       # Anon key only — safe for frontend
VITE_API_URL=                 # Render backend URL
```

---

## 11. Future Stack Additions (Post-Demo)

| Addition | Purpose | When |
|---|---|---|
| Angel One SmartAPI | Real client portfolio connection | Month 2 |
| Supabase Storage | Store PDF files permanently | Month 2 |
| Supabase Realtime | WebSocket for live report updates | Month 3 |
| Resend / SendGrid | Auto-email PDF to HNI client | Month 3 |
| Sarvam AI STT | Voice-to-query for Hindi RM interface | Month 4 |
| Redis | Caching frequently-fetched prices | When scale > 500 clients |
