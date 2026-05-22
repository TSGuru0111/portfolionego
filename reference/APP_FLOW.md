# PortfolioNarrator — Application Flow
**Version:** 1.0 | **Date:** May 2026

---

## 1. Overview of Flows

PortfolioNarrator has four distinct flows that run in parallel:

| Flow | Trigger | Who | Frequency |
|---|---|---|---|
| User Flow | Manual — RM action | Relationship Manager | On demand |
| Data Flow | On report generation | System | Per report |
| News Pipeline | Scheduled | System (EasyCron) | Daily / Weekly |
| Admin Flow | Manual — admin trigger | Dev / Admin | As needed |

---

## 2. User Flow — Relationship Manager Journey

### 2.1 Authentication

```
RM opens web app (Vercel URL)
        ↓
Login screen loads
        ↓
RM enters email + password
        ↓
Supabase Auth validates credentials
        ↓
JWT token issued → stored in localStorage
        ↓
React Router redirects to /dashboard
```

**Error states:**
- Wrong credentials → "Invalid email or password" toast
- Network failure → "Connection error, please retry" toast
- Session expired → redirect back to login with message

---

### 2.2 Client Dashboard

```
/dashboard loads
        ↓
React fetches GET /clients (FastAPI)
        ↓
FastAPI queries Supabase: SELECT * FROM clients WHERE rm_id = {current_rm}
        ↓
Returns list of HNI client cards
        ↓
Dashboard renders: name, AUM, risk profile, last report date, language badge
        ↓
RM can: search by name | filter by language | sort by AUM
        ↓
RM clicks a client card
        ↓
Navigate to /clients/{client_id}
```

---

### 2.3 Client Detail & Portfolio View

```
/clients/{client_id} loads
        ↓
React fetches GET /clients/{id}/portfolio (FastAPI)
        ↓
FastAPI:
    Step 1 → fetch client profile from Supabase (clients table)
    Step 2 → fetch holdings from Supabase (portfolios table)
    Step 3 → for each holding, call fetch_stock_price_safe(ticker)
        → Try yfinance first
        → On failure → use Supabase price_cache
        → If neither → mark as "unavailable"
    Step 4 → compute portfolio return vs Nifty 50
    Step 5 → return combined response
        ↓
React renders:
    - Client info card: name, AUM, risk profile, RM name, language
    - Holdings table: stock | qty | buy price | current price | return %
    - Portfolio summary: total value, total return %, alpha vs Nifty
    - Sector allocation donut chart
    - [Yellow banner if any prices are from cache]
    - [Generate Report] button
    - [Past Reports] list if reports exist
```

---

### 2.4 Report Generation (Core Flow)

```
RM clicks [Generate Report] for selected month
        ↓
React calls POST /reports/generate
    body: { client_id, month: "2026-04" }
        ↓
FastAPI: validate_context()
    → check holdings not empty
    → check portfolio_return not None
    → check nifty_return available
    → check client_name present
    → if invalid → return 400 with clear error message
        ↓
FastAPI: build_context_packet()
    → fetch client + portfolio from Supabase
    → fetch live prices via fetch_stock_price_safe()
    → fetch_client_relevant_news(client_id):
        → get top 3 holdings by value
        → get dominant 2 sectors
        → fetch stock-specific news via NewsAPI (per holding)
        → fetch sector news via GNews (per sector)
        → fetch weekly_summaries from Supabase (last 4 weeks)
        → fetch RBI RSS headlines
        → fetch Moneycontrol market RSS headlines
    → compute: portfolio_return, alpha, top_performers, underperformers
    → build context string
        ↓
FastAPI: build_prompt_safe(context)
    → estimate token count
    → if > 100,000 tokens → trim news to last week only
    → inject few-shot examples (2 real RM letters)
    → inject 7-section structure instructions
    → inject negative instructions (no generic phrases)
    → inject data context
        ↓
FastAPI: StreamingResponse → Cohere Command R+ (stream=True)
    → model: command-r-plus-08-2024
    → preamble: senior RM persona
    → stream tokens back to React
        ↓
React: reads stream with fetch() + ReadableStream
    → appends each token to report viewer in real time
    → letter types out live on screen
        ↓
Stream ends
        ↓
FastAPI (background): QA check call (non-blocking)
    → Cohere scores the letter 1-10
    → if score < 7:
        → regenerate with strict prompt
        → update report in Supabase
        → push updated version to frontend via WebSocket or polling
        ↓
FastAPI: save report to Supabase reports table
    → { client_id, month, generated_text, qa_score, created_at }
        ↓
React: show [Download PDF] button + [Toggle Hindi] button
```

---

### 2.5 Language Toggle (Hindi)

```
RM clicks [Generate Hindi Version]
        ↓
React calls POST /reports/{report_id}/translate
    body: { language: "hindi" }
        ↓
FastAPI: fetch English report from Supabase
        ↓
FastAPI: Cohere Command R+ translation call
    → preamble: expert financial translator persona
    → instructions:
        - Use formal 'Aap'
        - Keep numbers in English
        - Keep stock names in English
        - Map section headers to Hindi equivalents
        - No content changes — translation only
        ↓
FastAPI: save Hindi version to Supabase
    → { report_id, language: "hindi", translated_text }
        ↓
React: replace report viewer content with Hindi text
    → streaming again for same live feel
```

---

### 2.6 PDF Export

```
RM clicks [Download PDF]
        ↓
React calls GET /reports/{report_id}/export-pdf?lang=english
        ↓
FastAPI:
    Step 1 → fetch report text from Supabase
    Step 2 → fetch client profile (name, RM name, firm, designation)
    Step 3 → render Jinja2 HTML template with data
    Step 4 → load local fonts (Inter + Playfair Display .ttf files)
    Step 5 → WeasyPrint generates PDF bytes
        ↓
FastAPI returns:
    Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=..."}
    )
        ↓
Browser triggers file download
    → filename: "RajeshMehta_Portfolio_Report_April_2026.pdf"
```

---

## 3. News Pipeline Flow — Background Automation

### 3.1 Daily Collection (7:00 PM IST)

```
EasyCron.com hits → GET /jobs/collect-daily-news?secret={JOB_SECRET}
        ↓
FastAPI validates JOB_SECRET
        ↓
daily_news_collection() runs:
    ↓
    Fetch from 6 sources in parallel:
    ┌─────────────────────────────────────────────────────────┐
    │ Moneycontrol Markets RSS    → 5 headlines               │
    │ Economic Times Markets RSS  → 5 headlines               │
    │ RBI Press Release RSS       → 3 headlines               │
    │ NSE Corporate Actions RSS   → 3 headlines               │
    │ NewsAPI → "Nifty 50 India"  → 3 articles (free tier)   │
    │ GNews → "India stock market"→ 3 articles (free tier)    │
    └─────────────────────────────────────────────────────────┘
        ↓
    Tag each headline with category:
        market | regulatory | sector_IT | sector_BFSI |
        sector_Pharma | sector_FMCG | global
        ↓
    Insert all rows into Supabase daily_news table
        ↓
    Return {"status": "ok", "headlines_saved": N}
        ↓
    On any error → log_error("daily_news_collection", error)
```

---

### 3.2 Weekly Summarisation (Sunday 11:00 PM IST)

```
EasyCron.com hits → GET /jobs/weekly-summarise?secret={JOB_SECRET}
        ↓
FastAPI validates JOB_SECRET
        ↓
weekly_summarisation() runs:
        ↓
    Fetch past 7 days from daily_news table
        ↓
    Group by category
        ↓
    For each category (parallel calls):
        → Build headline list string
        → Cohere Command R (cheaper model):
            "Summarise these Indian financial headlines into
             3-4 sentences for an HNI investment report.
             Be specific. Reference actual events."
        → Returns 150-word summary per category
        ↓
    Save to weekly_summaries table:
        { week_start, week_end, summaries: {JSONB} }
        ↓
    On any error → log_error("weekly_summarisation", error)
```

---

### 3.3 Monthly Report Auto-Generation (Last Day of Month, 6:00 AM IST)

```
EasyCron.com hits → GET /jobs/generate-monthly-reports?secret={JOB_SECRET}
        ↓
FastAPI validates JOB_SECRET
        ↓
Fetch all active clients from Supabase
        ↓
For each client (sequential, not parallel — avoid rate limits):
    → generate_report(client_id, current_month)
    → save to reports table
    → log success
    → wait 2 seconds between clients
        ↓
Return {"status": "ok", "reports_generated": N, "errors": [...]}
```

---

## 4. Data Flow — Inside Report Generation

```
CLIENT DATA (Supabase)          MARKET DATA (yfinance)       NEWS DATA (Supabase)
      ↓                                ↓                            ↓
client.name                    fetch_stock_price_safe()      weekly_summaries
client.aum                     → TCS.NS, INFY.NS, etc.      → market summary
client.language                → Nifty 50 return            → regulatory summary
client.tone_pref               → USD/INR change             → sector_IT summary
holdings[]                     → crude oil change           → sector_BFSI summary
rm_name, rm_email              [fallback: price_cache]
      ↓                                ↓                            ↓
      └──────────────────────────────────────────────────────────────┘
                                       ↓
                            build_context_packet()
                                       ↓
                    ┌──────────────────────────────────────┐
                    │ portfolio_return: 4.2%               │
                    │ nifty_return: 3.1%                   │
                    │ alpha: +1.1%                         │
                    │ top_performers: [TCS +8.3%, HDFC +6.7%]│
                    │ underperformers: [Paytm -11%]        │
                    │ market_summary: "RBI held at 6.5%..."│
                    │ sector_IT_news: "US demand recovery.."|
                    │ rbi_update: "Neutral stance..."      │
                    │ usdinr_change: +2.1%                 │
                    └──────────────────────────────────────┘
                                       ↓
                            build_prompt_safe()
                            → estimate_tokens()
                            → inject few-shot examples
                            → inject context
                            → inject negative instructions
                                       ↓
                         Cohere Command R+ (stream)
                                       ↓
                            7-Section RM Letter
                                       ↓
                    ┌──────────────────────────────────────┐
                    │ QA Check (Cohere Call 2)             │
                    │ Score < 7 → regenerate with strict   │
                    │ Score ≥ 7 → proceed                  │
                    └──────────────────────────────────────┘
                                       ↓
                    Save to Supabase reports table
                                       ↓
                    Return to React (streaming complete)
                                       ↓
                    ┌──────────────────────────────────────┐
                    │ Optional: Hindi translation call      │
                    │ → 2-step: English → formal Hindi     │
                    └──────────────────────────────────────┘
                                       ↓
                    PDF export (WeasyPrint + Jinja2)
                                       ↓
                    Download to RM's device
```

---

## 5. Admin Flow

```
RM / Admin opens /admin
        ↓
Admin panel shows:
    [Collect News Now]       → POST /admin/trigger-news-collection
    [Run Weekly Summary]     → POST /admin/trigger-weekly-summary
    [Generate All Reports]   → POST /admin/trigger-all-reports
    [View Error Log]         → GET  /admin/errors (last 20)
    [DB Health Check]        → GET  /admin/health
        ↓
All admin endpoints protected with ADMIN_SECRET env var
```

---

## 6. Error Handling Flow

```
Any background job fails
        ↓
Exception caught in try/except
        ↓
log_error(job_name, error_message, context_dict)
        ↓
Insert into Supabase error_logs table:
    { job, error, context, timestamp }
        ↓
Job returns 200 with {"status": "error", "logged": true}
    (EasyCron does not retry on error — prevents cascading failures)
        ↓
Admin checks /admin/errors next working day
```

```
yfinance fetch fails
        ↓
fetch_stock_price_safe() catches exception
        ↓
Queries Supabase price_cache for last known price
        ↓
Returns { price, source: "cached", cached_at }
        ↓
React shows yellow banner:
    "Some prices are as of [date] — live feed temporarily unavailable"
        ↓
Report still generates with disclaimer added automatically
```

```
Cohere returns invalid JSON (QA check)
        ↓
safe_parse_json() strips markdown fences
        ↓
Searches for { } pattern with regex
        ↓
On parse failure → returns { score: 8, weakest_section: null }
        ↓
Pipeline continues — does not crash
```

---

## 7. Screen Map

```
/login                  → Authentication screen
/dashboard              → Client list + search + filter
/clients/:id            → Client detail + portfolio + Generate button
/clients/:id/report/:rid → Report viewer + language toggle + PDF download
/admin                  → Manual triggers + error log + health check
```
