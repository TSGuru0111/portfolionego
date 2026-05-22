# PortfolioNarrator — Backend Structure
**Version:** 1.0 | **Date:** May 2026

---

## 1. Folder Structure

```
backend/
├── main.py                         # FastAPI app init + CORS + router registration
├── requirements.txt
├── .env                            # Environment variables (never commit)
├── render.yaml                     # Render deployment config
│
├── routes/                         # API route handlers (thin — business logic in services)
│   ├── __init__.py
│   ├── clients.py                  # GET /clients, GET /clients/{id}/portfolio
│   ├── reports.py                  # POST /reports/generate-stream, GET /reports
│   │                               # POST /reports/{id}/translate
│   │                               # GET /reports/{id}/export-pdf
│   ├── jobs.py                     # GET /jobs/collect-daily-news
│   │                               # GET /jobs/weekly-summarise
│   │                               # GET /jobs/generate-monthly
│   ├── admin.py                    # POST /admin/trigger-*
│   │                               # GET /admin/errors
│   │                               # GET /admin/health
│   └── auth.py                     # POST /auth/logout (Supabase handles login)
│
├── services/                       # Business logic — all heavy lifting here
│   ├── __init__.py
│   ├── market_data.py              # yfinance fetching + price_cache fallback
│   ├── news_fetcher.py             # RSS + NewsAPI + GNews fetching
│   ├── summariser.py               # Weekly summarisation via Cohere Command R
│   ├── context_builder.py          # Assembles full context packet for LLM
│   ├── prompt_builder.py           # Builds final prompt with few-shot examples
│   ├── report_generator.py         # Cohere streaming + QA pipeline
│   ├── translator.py               # Hindi translation via Cohere
│   ├── pdf_exporter.py             # WeasyPrint + Jinja2 PDF generation
│   └── error_logger.py             # Supabase error_logs writer
│
├── db/                             # Database operations
│   ├── __init__.py
│   ├── supabase_client.py          # Supabase client singleton
│   ├── clients_db.py               # Client + portfolio CRUD
│   ├── news_db.py                  # daily_news + weekly_summaries CRUD
│   ├── reports_db.py               # Reports CRUD
│   └── cache_db.py                 # price_cache + error_logs CRUD
│
├── models/                         # Pydantic request/response models
│   ├── __init__.py
│   ├── client.py                   # ClientResponse, PortfolioResponse
│   ├── report.py                   # GenerateReportRequest, ReportResponse
│   └── job.py                      # JobResponse
│
├── utils/                          # Pure utility functions
│   ├── __init__.py
│   ├── formatters.py               # Number formatting, date helpers
│   ├── json_safe.py                # safe_parse_json()
│   ├── token_counter.py            # estimate_tokens()
│   └── validators.py               # validate_context()
│
└── static/
    ├── fonts/                      # Locally hosted fonts for WeasyPrint
    │   ├── Inter-Regular.ttf
    │   ├── Inter-Bold.ttf
    │   └── PlayfairDisplay-Bold.ttf
    └── templates/
        └── letter_template.html    # Jinja2 PDF template
```

---

## 2. main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from routes import clients, reports, jobs, admin, auth

app = FastAPI(
    title="PortfolioNarrator API",
    version="1.0.0",
    docs_url="/docs",       # Disable in production
    redoc_url="/redoc",
)

# ── CORS — MUST be first, before any routes ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",                          # Vite dev
        "http://localhost:3000",                          # CRA dev
        os.getenv("FRONTEND_URL", ""),                   # Vercel prod
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files (fonts) ──
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── Routers ──
app.include_router(auth.router,    prefix="/auth",    tags=["Auth"])
app.include_router(clients.router, prefix="/clients", tags=["Clients"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
app.include_router(jobs.router,    prefix="/jobs",    tags=["Jobs"])
app.include_router(admin.router,   prefix="/admin",   tags=["Admin"])

# ── Health check (UptimeRobot pings this) ──
@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
```

---

## 3. Key Service Files

### 3.1 services/market_data.py

```python
import yfinance as yf
from datetime import datetime
from db.cache_db import get_cached_price, save_price_cache
from services.error_logger import log_error

async def fetch_stock_price_safe(ticker: str) -> dict:
    """
    Fetch live NSE stock price via yfinance.
    Falls back to Supabase price_cache on failure.
    Returns source: 'live' | 'cached' | 'unavailable'
    """
    try:
        stock = yf.Ticker(f"{ticker}.NS")
        hist  = stock.history(period="2d")

        if hist.empty:
            raise ValueError(f"Empty response for {ticker}")

        price      = float(hist['Close'].iloc[-1])
        prev_close = float(hist['Close'].iloc[0])
        change_pct = ((price - prev_close) / prev_close) * 100

        await save_price_cache(ticker, price, change_pct)

        return {
            "ticker": ticker, "price": price,
            "change_pct": round(change_pct, 2),
            "source": "live"
        }

    except Exception as e:
        await log_error("fetch_stock_price", str(e), {"ticker": ticker})
        cached = await get_cached_price(ticker)
        if cached:
            return { **cached, "source": "cached" }
        return {"ticker": ticker, "price": None, "source": "unavailable"}


async def fetch_nifty_return(period: str = "1mo") -> float | None:
    """Returns Nifty 50 return % for the given period."""
    try:
        nifty = yf.Ticker("^NSEI")
        hist  = nifty.history(period=period)
        if hist.empty:
            return None
        start = float(hist['Close'].iloc[0])
        end   = float(hist['Close'].iloc[-1])
        return round(((end - start) / start) * 100, 2)
    except Exception as e:
        await log_error("fetch_nifty_return", str(e))
        return None


async def fetch_macro_data() -> dict:
    """Fetch USD/INR and crude oil change for context."""
    result = {}
    try:
        usdinr = yf.Ticker("INR=X").history(period="1mo")
        if not usdinr.empty:
            start = float(usdinr['Close'].iloc[0])
            end   = float(usdinr['Close'].iloc[-1])
            result["usdinr_change"] = round(((end - start) / start) * 100, 2)
    except:
        result["usdinr_change"] = None

    try:
        crude = yf.Ticker("CL=F").history(period="1mo")
        if not crude.empty:
            start = float(crude['Close'].iloc[0])
            end   = float(crude['Close'].iloc[-1])
            result["crude_change"] = round(((end - start) / start) * 100, 2)
    except:
        result["crude_change"] = None

    return result
```

---

### 3.2 services/news_fetcher.py

```python
import feedparser
import requests
import os
from datetime import date

FEEDS = {
    "market_mc":  "https://www.moneycontrol.com/rss/marketreports.xml",
    "market_et":  "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "economy_et": "https://economictimes.indiatimes.com/news/economy/rssfeeds/20812518.cms",
    "rbi":        "https://www.rbi.org.in/feeds/pressReleases.xml",
    "nse":        "https://www.nseindia.com/static/rss-feed",
}

def fetch_rss(url: str, limit: int = 5) -> list[dict]:
    """Fetch headlines from an RSS feed. Returns empty list on failure."""
    try:
        feed = feedparser.parse(url)
        return [
            {
                "headline": entry.get("title", ""),
                "summary":  entry.get("summary", "")[:300],
                "source":   url,
            }
            for entry in feed.entries[:limit]
        ]
    except:
        return []


def fetch_newsapi(query: str, limit: int = 3) -> list[str]:
    """Fetch stock-specific news from NewsAPI.org."""
    try:
        response = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q":        query,
                "language": "en",
                "sortBy":   "publishedAt",
                "pageSize": limit,
                "apiKey":   os.getenv("NEWSAPI_KEY"),
            },
            timeout=5,
        )
        articles = response.json().get("articles", [])
        return [
            f"{a['title']} — {a.get('description', '')[:150]}"
            for a in articles
        ]
    except:
        return []


def fetch_gnews(sector: str, limit: int = 3) -> list[str]:
    """Fetch sector news from GNews API."""
    try:
        response = requests.get(
            "https://gnews.io/api/v4/search",
            params={
                "q":      f"{sector} sector India stock market",
                "lang":   "en",
                "country":"in",
                "max":    limit,
                "apikey": os.getenv("GNEWS_API_KEY"),
            },
            timeout=5,
        )
        return [
            a["title"]
            for a in response.json().get("articles", [])
        ]
    except:
        return []


async def fetch_client_relevant_news(client_id: str, portfolio: dict) -> dict:
    """
    Portfolio-aware news fetching.
    Fetches news specific to the client's actual holdings and sectors.
    """
    from db.news_db import get_recent_weekly_summaries

    # Get top 3 holdings by value
    holdings = sorted(
        portfolio.get("holdings", []),
        key=lambda h: h.get("qty", 0) * h.get("current_price", 0),
        reverse=True
    )[:3]

    # Get dominant sectors
    sector_counts = {}
    for h in portfolio.get("holdings", []):
        s = h.get("sector", "Other")
        sector_counts[s] = sector_counts.get(s, 0) + 1
    dominant_sectors = sorted(sector_counts, key=sector_counts.get, reverse=True)[:2]

    news = {}

    # Stock-specific news
    for holding in holdings:
        ticker = holding.get("ticker", "")
        company = holding.get("company_name", ticker)
        news[f"stock_{ticker}"] = fetch_newsapi(
            f"{company} NSE India results", limit=2
        )

    # Sector news
    for sector in dominant_sectors:
        news[f"sector_{sector}"] = fetch_gnews(sector, limit=2)

    # Always include macro + regulatory
    news["macro"]      = fetch_rss(FEEDS["market_mc"], limit=4)
    news["regulatory"] = fetch_rss(FEEDS["rbi"], limit=2)

    # Pre-compressed weekly summaries (from scheduler)
    summaries = await get_recent_weekly_summaries(weeks=4)
    news["weekly_summaries"] = summaries

    return news
```

---

### 3.3 services/report_generator.py

```python
import cohere
import os
from typing import AsyncGenerator
from utils.json_safe import safe_parse_json
from utils.validators import validate_context
from services.prompt_builder import build_prompt_safe
from services.error_logger import log_error
from db.reports_db import save_report

co = cohere.Client(api_key=os.getenv("COHERE_API_KEY"))

PREAMBLE = """
You are Priya Sharma, a Senior Relationship Manager at a leading Indian
private wealth management firm with 12 years of experience managing
HNI and UHNI client portfolios. You write warm, specific, data-driven
quarterly and monthly portfolio review letters. Your writing is
professional yet personal — clients feel you wrote this specifically
for them, not from a template.

CRITICAL RULES:
- NEVER use these phrases: 'market volatility', 'challenging environment',
  'headwinds', 'uncertain times', 'it is worth noting', 'needless to say'
- ALWAYS reference specific stock names, specific percentages, specific events
- NEVER invent any numbers — use ONLY the data provided
- Every section must be specific to THIS client's portfolio
"""

async def generate_report_stream(
    client_id: str,
    context: dict,
) -> AsyncGenerator[str, None]:
    """
    Streams the generated RM letter token by token.
    Runs QA check in background after streaming completes.
    """
    # Validate before calling LLM
    is_valid, reason = validate_context(context)
    if not is_valid:
        raise ValueError(reason)

    prompt = build_prompt_safe(context)

    full_text = ""

    try:
        # Streaming call to Cohere Command R+
        for event in co.chat_stream(
            model="command-r-plus-08-2024",
            message=prompt,
            preamble=PREAMBLE,
            temperature=0.7,    # Some creativity, but grounded
        ):
            if event.event_type == "text-generation":
                chunk = event.text
                full_text += chunk
                yield chunk

    except Exception as e:
        await log_error("report_generator", str(e), {"client_id": client_id})
        raise

    # QA check (non-blocking — runs after stream completes)
    qa_score = await run_qa_check(full_text)

    # If quality is too low, regenerate (non-streaming, replace in DB)
    if qa_score < 7:
        full_text = await regenerate_strict(context, qa_score)

    # Save final report
    await save_report(client_id, context["month"], full_text, qa_score)


async def run_qa_check(letter_text: str) -> int:
    """Score the letter 1-10. Returns 8 on parse failure (safe default)."""
    try:
        response = co.chat(
            model="command-r-plus-08-2024",
            message=f"""
            Score this Indian wealth management letter from 1-10.
            Criteria:
            1. Is it personalised to a specific client? (not generic)
            2. Does it reference specific stock names and percentages?
            3. Does it avoid phrases like 'market volatility'?
            4. Does it have all 7 sections?
            5. Does it feel like a real RM wrote it?

            Return ONLY JSON (no preamble, no markdown):
            {{"score": 8, "weakest_section": "Section 3",
              "reason": "brief reason"}}

            Letter:
            {letter_text[:3000]}
            """,
            temperature=0.1,    # Deterministic for scoring
        )
        result = safe_parse_json(response.text)
        return result.get("score", 8)
    except:
        return 8  # Safe default — don't crash pipeline on QA failure


async def regenerate_strict(context: dict, original_score: int) -> str:
    """Regenerate with stricter prompt when QA score is below 7."""
    from services.prompt_builder import build_strict_prompt
    strict_prompt = build_strict_prompt(context, note=f"Previous score was {original_score}/10. Be MORE specific.")

    response = co.chat(
        model="command-r-plus-08-2024",
        message=strict_prompt,
        preamble=PREAMBLE,
        temperature=0.5,
    )
    return response.text
```

---

### 3.4 services/translator.py

```python
import cohere, os

co = cohere.Client(api_key=os.getenv("COHERE_API_KEY"))

HINDI_HEADERS = {
    "Personal Greeting":        "व्यक्तिगत अभिवादन",
    "Performance Summary":      "प्रदर्शन सारांश",
    "What Drove Performance":   "प्रदर्शन के मुख्य कारण",
    "Market Context":           "बाज़ार परिदृश्य",
    "Underperformers":          "कमज़ोर प्रदर्शन",
    "Outlook & Recommendations":"दृष्टिकोण और सुझाव",
    "Personal Close":           "व्यक्तिगत समापन",
}

async def translate_to_hindi(english_letter: str) -> str:
    """
    Two-step translation: English RM letter → formal Hindi.
    Preserves numbers, stock names, ₹ amounts in English.
    """
    import json

    response = co.chat(
        model="command-r-plus-08-2024",
        message=f"""
        Translate this professional Indian wealth management letter
        into formal Hindi.

        STRICT RULES:
        1. Use formal 'Aap' (आप) — NEVER 'Tum' or 'Tu'
        2. Keep ALL numbers in English: ₹2.47 crore, 4.2%, etc.
        3. Keep ALL stock names in English: TCS, HDFC Bank, Nifty 50
        4. Keep ₹ symbol as-is
        5. Replace section headers with these exact Hindi equivalents:
           {json.dumps(HINDI_HEADERS, ensure_ascii=False, indent=2)}
        6. Do NOT add any content not in the original
        7. Do NOT explain the translation — output ONLY the Hindi letter
        8. The Hindi must read naturally — not like a translated document

        English letter to translate:
        {english_letter}
        """,
        preamble="""
        You are an expert financial translator specialising in Indian
        wealth management documents. Your Hindi is fluent, formal,
        and reads as if originally written in Hindi — never like a translation.
        """,
        temperature=0.3,
    )

    return response.text
```

---

### 3.5 utils/validators.py

```python
def validate_context(context: dict) -> tuple[bool, str]:
    """
    Validate context packet before sending to LLM.
    Returns (is_valid, error_message).
    """
    if not context.get("client_name"):
        return False, "Client name is missing"

    holdings = context.get("holdings", [])
    if not holdings:
        return False, "Portfolio has no holdings — cannot generate report"

    if context.get("portfolio_return") is None:
        return False, "Could not compute portfolio return — check price data"

    if context.get("nifty_return") is None:
        return False, "Nifty benchmark data unavailable — try again later"

    unavailable = [
        h["ticker"] for h in holdings
        if h.get("source") == "unavailable"
    ]
    if len(unavailable) > len(holdings) * 0.5:
        return False, f"Price data unavailable for too many holdings: {unavailable}"

    return True, "OK"
```

---

### 3.6 utils/json_safe.py

```python
import json, re

def safe_parse_json(raw: str) -> dict:
    """
    Safely parse JSON from Cohere output.
    Handles markdown fences, preamble text, and malformed output.
    Always returns a dict — never raises.
    """
    # Strip markdown code fences
    cleaned = re.sub(r"```json|```", "", raw).strip()

    # Extract first JSON object found
    match = re.search(r"\{.*?\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group()

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        # Return safe defaults — pipeline continues
        return {
            "score":           8,
            "weakest_section": None,
            "reason":          "json_parse_error",
        }
```

---

### 3.7 services/error_logger.py

```python
from datetime import datetime
from db.supabase_client import get_supabase

async def log_error(job: str, error: str, context: dict = {}) -> None:
    """
    Log errors to Supabase error_logs table.
    Never raises — errors in error logging must not crash the main pipeline.
    """
    try:
        supabase = get_supabase()
        await supabase.table("error_logs").insert({
            "job":       job,
            "error":     str(error)[:1000],  # Truncate very long errors
            "context":   context,
            "timestamp": datetime.now().isoformat(),
        }).execute()
    except:
        # Last resort — print to Render logs
        print(f"[ERROR LOG FAILED] {job}: {error}")
```

---

## 4. Route Examples

### 4.1 routes/reports.py

```python
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, Response
from models.report import GenerateReportRequest
from services.context_builder import build_context_packet
from services.report_generator import generate_report_stream
from services.translator import translate_to_hindi
from services.pdf_exporter import generate_pdf
from db.reports_db import get_report, get_reports_for_client
from auth import get_current_rm

router = APIRouter()

@router.post("/generate-stream")
async def generate_report(
    request: GenerateReportRequest,
    rm = Depends(get_current_rm),
):
    """Stream the generated RM letter token by token."""
    try:
        context = await build_context_packet(
            request.client_id, request.month
        )
        return StreamingResponse(
            generate_report_stream(request.client_id, context),
            media_type="text/plain",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Report generation failed")


@router.post("/{report_id}/translate")
async def translate_report(
    report_id: str,
    language: str = "hindi",
    rm = Depends(get_current_rm),
):
    """Translate an existing report to Hindi."""
    report = await get_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")

    hindi_text = await translate_to_hindi(report["generated_text"])
    return {"hindi_text": hindi_text}


@router.get("/{report_id}/export-pdf")
async def export_pdf(
    report_id: str,
    lang: str = "english",
    rm = Depends(get_current_rm),
):
    """Generate and return PDF for download."""
    report = await get_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")

    text = report["hindi_text"] if lang == "hindi" else report["generated_text"]
    pdf_bytes = await generate_pdf(report_id, text)

    client_name = report["client_name"].replace(" ", "")
    month       = report["month"].replace("-", "_")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
            f'attachment; filename="{client_name}_Report_{month}.pdf"'
        }
    )
```

---

## 5. requirements.txt

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
pydantic==2.7.0
python-dotenv==1.0.1
cohere==5.5.0
yfinance==0.2.40
feedparser==6.0.11
requests==2.32.2
supabase==2.4.0
weasyprint==62.1
jinja2==3.1.4
python-multipart==0.0.9
```

---

## 6. render.yaml

```yaml
services:
  - type: web
    name: portfolionarrator-backend
    env: python
    buildCommand: |
      apt-get update &&
      apt-get install -y libpango-1.0-0 libpangocairo-1.0-0
        libcairo2 libffi-dev shared-mime-info &&
      pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_KEY
        sync: false
      - key: COHERE_API_KEY
        sync: false
      - key: NEWSAPI_KEY
        sync: false
      - key: GNEWS_API_KEY
        sync: false
      - key: JOB_SECRET
        sync: false
      - key: ADMIN_SECRET
        sync: false
      - key: FRONTEND_URL
        sync: false
```
