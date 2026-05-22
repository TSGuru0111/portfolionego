# PortfolioNarrator — Product Requirements Document (PRD)
**Version:** 1.0  
**Date:** May 2026  
**Status:** Active Development  
**Target Launch:** 2-week demo build → production MVP Month 2

---

## 1. Executive Summary

PortfolioNarrator is an AI-powered quarterly and monthly portfolio commentary platform built specifically for Indian wealth management firms, PMS (Portfolio Management Service) providers, and independent RIAs (Registered Investment Advisers).

It solves one specific, painful problem: **Relationship Managers (RMs) spend 10–12 hours manually writing personalised portfolio review letters for each HNI client every quarter.** A firm with 200 clients spends 2,000+ hours per quarter on this task alone — work that is repetitive, inconsistent, and takes RMs away from actual client relationship work.

PortfolioNarrator reduces this to **under 60 seconds per client** by automatically fetching live portfolio data, real market context, and stock-specific news — then generating a personalised, 7-section RM letter using Cohere Command R+ — indistinguishable from one written by a senior wealth manager.

---

## 2. Problem Statement

### 2.1 The Manual Process Today

A typical Indian PMS/wealth management firm's quarterly reporting workflow:

| Step | Who Does It | Time |
|---|---|---|
| Pull portfolio data from PMS system | RM / Operations | 1–2 hrs |
| Compute returns vs benchmark manually | RM | 30 mins |
| Research market events for the quarter | RM | 1–2 hrs |
| Write narrative commentary per client | RM | 3–4 hrs |
| Customise tone/language per client | RM | 30 mins |
| Senior review and approval | Senior RM / Head | 1 hr |
| Format, brand, send | Operations | 30 mins |
| **Total per client** | | **~10–12 hours** |

For a firm with 200 HNI clients: **2,000–2,400 hours every quarter** — roughly 300 working days compressed into a 2-week reporting window.

### 2.2 Why This Matters for HNI Clients

India's HNI population is growing rapidly. As of 2024, India has 850,000+ HNIs managing ₹30+ lakh crore through PMS alone, with the UHNI population growing 6% annually. Every HNI client expects:
- Personalised letters — not generic templates
- Explanation of *why* their portfolio performed the way it did
- Market context relevant to *their specific holdings*
- Communication in their preferred language (English or Hindi)
- Professional, branded PDF format

The reporting burden doubles as the client book doubles. PortfolioNarrator keeps effort flat regardless of client count.

### 2.3 The Gap in Existing Solutions

| Solution | Limitation |
|---|---|
| Excel templates | Still manual writing, no AI |
| Generic report generators | Template-feel, no personalisation |
| US-based AI writing tools | No Indian market context, data offshore (DPDP risk) |
| Large PMS software | Expensive, generic output, no LLM integration |

---

## 3. Target Users

### 3.1 Primary User — Relationship Manager (RM)
- **Profile:** 2–15 years experience, manages 30–200 HNI clients
- **Pain:** Spends 2 weeks per quarter on report writing instead of client calls
- **Goal:** Generate a professional, personalised letter for each client in under 60 seconds
- **Tech comfort:** Moderate — uses Excel, CRM, email. Not a developer.
- **Language:** English primarily; some need Hindi output for clients

### 3.2 Secondary User — Head of Wealth / CTO of PMS Firm
- **Profile:** Decision maker, evaluates and purchases the tool
- **Pain:** Team productivity loss, inconsistent report quality, compliance risk
- **Goal:** Standardise reporting quality, reduce ops costs, impress HNI clients
- **Buys based on:** ROI (time saved), letter quality, data security (DPDP), demo

### 3.3 End Beneficiary — HNI Client
- **Profile:** ₹50L–₹100 Cr investable assets, expects premium service
- **Receives:** Personalised PDF letter from their RM every quarter/month
- **Does not interact with the product directly**
- **Judges quality by:** Personalisation, accuracy, clarity, language preference

---

## 4. Product Goals

### 4.1 Primary Goals (Demo — 2 weeks)
- [ ] Generate a complete 7-section RM letter for any client in under 60 seconds
- [ ] Letter uses live market data — not hardcoded or stale information
- [ ] Letter is meaningfully different per client — not a template fill
- [ ] PDF download is professional, branded, and print-ready
- [ ] Hindi language toggle works fluently for at least 1 client profile
- [ ] 5 synthetic HNI client profiles produce 5 visually different reports

### 4.2 Secondary Goals (MVP — Month 2)
- [ ] Real client portfolio data connectable via CSV upload or broker API
- [ ] Automated monthly report generation for all clients on last day of month
- [ ] Daily news pipeline running without manual intervention
- [ ] RM can edit generated sections before downloading
- [ ] Multi-RM support with client assignment

### 4.3 Business Goals
- Close first paid client within 30 days of demo
- Target: Independent MFDs and small RIAs (50–200 clients) as first segment
- Pricing: ₹10–30L one-time build + ₹2–5L/month managed service

---

## 5. Features

### 5.1 Core Features (Must Have — 2-week build)

#### F1 — Client Dashboard
- List of all HNI clients with AUM, risk profile, last report date
- Search and filter by name, AUM range, language preference
- Click to open client detail

#### F2 — Portfolio Viewer
- Display client holdings: stock name, quantity, buy price, current price, return %
- Portfolio total return vs Nifty 50 benchmark
- Visual breakdown: sector allocation, asset class split
- Price cache fallback with yellow banner if yfinance is unavailable

#### F3 — AI Report Generator
- One-click report generation per client per month/quarter
- Streaming output — letter types out live on screen (not 20-second blank wait)
- Two-call pipeline: generate → quality check → regenerate if score < 7
- Input validation: block generation if portfolio data is incomplete

#### F4 — 7-Section RM Letter
- Section 1: Personalised greeting (name, tone, language)
- Section 2: Performance summary (numbers in plain English)
- Section 3: What drove performance (stock-specific + macro linkage)
- Section 4: Market context (RBI, FII flows, sector events)
- Section 5: Underperformers (honest, specific, with action plan)
- Section 6: Outlook and recommendations (3 actionable bullet points)
- Section 7: Personal close with RM name and call to action

#### F5 — Language Toggle
- English (default) and Hindi
- Two-step pipeline: generate English → translate to Hindi
- Hindi section headers mapped explicitly (not left in English)
- Numbers, stock names, ₹ amounts stay in English within Hindi text

#### F6 — PDF Export
- Branded PDF with firm logo placeholder, RM name, designation
- Professional typography using locally-hosted fonts (not CDN)
- Disclaimer footer (regulatory requirement)
- Filename: `[ClientName]_Portfolio_Report_[Month]_[Year].pdf`

#### F7 — Admin Panel
- Manual trigger: Collect News Now, Run Weekly Summary, Generate All Reports
- Error log viewer: see last 20 errors from background jobs
- Supabase health check: confirm DB connection is live

### 5.2 Background Features (Must Have — runs automatically)

#### F8 — Daily News Collection (7pm IST)
- Sources: Moneycontrol RSS, ET RSS, GNews API, NewsAPI.org, RBI RSS, NSE RSS
- Collection is portfolio-aware: fetches sector and stock-specific news
- Stores raw headlines in `daily_news` Supabase table
- Wrapped in try/except with error logging

#### F9 — Weekly Summarisation (Sunday 11pm IST)
- Compresses 7 days of headlines per category into 150-word summary using Cohere Command R
- Saves to `weekly_summaries` table
- Categories: market, regulatory, sector_IT, sector_BFSI, sector_Pharma, sector_FMCG, global

#### F10 — Price Cache
- Caches last successful yfinance price fetch per stock in Supabase
- Used as fallback when yfinance is unavailable
- Timestamp shown in UI when cached price is used

### 5.3 Future Features (Post-Demo — Month 2+)

| Feature | Priority | Notes |
|---|---|---|
| Angel One / Zerodha OAuth integration | High | Real client portfolio connection |
| CSV portfolio upload | High | Manual import path |
| RM editable sections | High | Before PDF download |
| Multi-RM login with client assignment | Medium | For larger firms |
| WhatsApp delivery of reports | Medium | Direct to HNI client |
| Marathi / Tamil language support | Medium | Expand vernacular |
| Automated email dispatch | Low | After editing approval |
| SEBI audit trail export | Low | Compliance requirement |

---

## 6. Non-Functional Requirements

### 6.1 Performance
- Report generation: < 60 seconds end-to-end (streaming starts within 3 seconds)
- Dashboard load: < 2 seconds
- PDF generation: < 10 seconds
- API response time: < 500ms for all non-LLM endpoints

### 6.2 Security
- All API keys stored in environment variables — never hardcoded
- Supabase Row Level Security (RLS) enabled per RM
- DPDP Act 2023 compliance: client PII stored only in Supabase (India-region)
- Job endpoints protected with secret key (`JOB_SECRET` env var)
- CORS restricted to known frontend origins only

### 6.3 Reliability
- yfinance fallback to Supabase price cache on failure
- Cohere JSON parsing with safe fallback (no crashes on malformed output)
- All background jobs wrapped in try/except with Supabase error logging
- Supabase health check prevents project pause (free tier management)

### 6.4 Data Integrity
- Never use LLM-generated numbers — all financial figures from fetched data only
- Prompt explicitly instructs: "Use ONLY the data provided. Do NOT invent any numbers."
- Price cache timestamps displayed when stale data is used
- Context validation before every LLM call

### 6.5 Compliance
- Data stored in Supabase (India-region or EU — confirm before production)
- No client PII sent to Cohere beyond what is in the prompt
- Regulatory disclaimer on every generated letter and PDF
- Error logs retained for 90 days

---

## 7. Success Metrics

| Metric | Target (Demo) | Target (MVP) |
|---|---|---|
| Report generation time | < 60 seconds | < 45 seconds |
| Letter quality score (internal QA) | > 7/10 | > 8.5/10 |
| Hindi letter fluency | Readable, no Hinglish | Native-feeling |
| PDF professional rating (team review) | Pass | Client-sendable |
| Zero crashes in 10-run demo | ✅ | ✅ |
| Client pays for pilot | — | 1 client in 30 days |

---

## 8. Constraints

- **Budget:** $2,500 Cohere credits (production tier — no rate limit issues)
- **Team:** 3 people (You + Dev 2 + Dev 3)
- **Timeline:** 14 days to working demo
- **No Claude API:** Cohere Command R+ for all LLM tasks
- **Free hosting:** Vercel (frontend) + Render (backend) — with UptimeRobot to prevent spin-down
- **No broker API integration in demo:** yfinance + synthetic Supabase data only

---

## 9. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Letter quality too generic | High | High | Few-shot examples + QA second call + negative instructions |
| yfinance breaks | Medium | High | Supabase price cache fallback |
| WeasyPrint font failures | High | Medium | Local fonts, system dependencies pre-installed |
| CORS blocks React↔FastAPI | High | High | CORSMiddleware on Day 1 before any routes |
| Render spins down during demo | High | High | UptimeRobot ping every 10 min |
| Cohere returns invalid JSON | Medium | Medium | `safe_parse_json()` with fallback |
| APScheduler dies on restart | High | Medium | EasyCron.com HTTP triggers instead |
| Hindi headers stay in English | Medium | Medium | Explicit header mapping dict in translation prompt |
| Supabase project pauses | Low | High | Daily health check query |
| Context window overflow | Low | Low | Token estimator + context trimmer |
