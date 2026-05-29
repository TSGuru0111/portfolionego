"""
PortfolioNarrator — FastAPI app entry.

The CORSMiddleware MUST be added before any route inclusions.
"""
from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque
from typing import Deque

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

app = FastAPI(
    title="PortfolioNarrator API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS — MUST be first ───
_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]
_frontend_url = os.getenv("FRONTEND_URL")
if _frontend_url:
    _origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request logging + simple in-memory rate limit ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("portfolionarrator")

# Rate limit: per-client-IP report generations.
_RATE_LIMIT_WINDOW_S = 3600
_RATE_LIMIT_MAX = 20
_rate_bucket: dict[str, Deque[float]] = defaultdict(deque)


def _rate_limited(key: str) -> bool:
    now = time.time()
    bucket = _rate_bucket[key]
    while bucket and now - bucket[0] > _RATE_LIMIT_WINDOW_S:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT_MAX:
        return True
    bucket.append(now)
    return False


@app.middleware("http")
async def request_logger_and_limiter(request: Request, call_next):
    started = time.monotonic()
    path = request.url.path
    method = request.method

    # Rate-limit only the expensive generate-stream endpoint.
    if method == "POST" and path.endswith("/reports/generate-stream"):
        client = request.client.host if request.client else "unknown"
        if _rate_limited(client):
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Rate limit exceeded "
                        f"({_RATE_LIMIT_MAX}/hour). Try again later."
                    )
                },
            )

    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled exception in %s %s", method, path)
        raise

    duration_ms = int((time.monotonic() - started) * 1000)
    # Skip noisy keep-alive log for /health.
    if path != "/health":
        log.info(
            "%s %s -> %s in %dms",
            method,
            path,
            response.status_code,
            duration_ms,
        )
    return response


# ─── Static files (fonts, templates) ───
app.mount("/static", StaticFiles(directory="static"), name="static")

# ─── Routers ───
from routes import admin, auth, clients, config, jobs, reports, wealth  # noqa: E402

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(clients.router, prefix="/clients", tags=["Clients"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(config.router, prefix="/config", tags=["Config"])
app.include_router(wealth.router, tags=["Wealth"])


@app.get("/health", tags=["Health"])
async def health() -> dict[str, str]:
    """Lightweight health check — used by EasyCron keep-alive."""
    return {"status": "ok"}
