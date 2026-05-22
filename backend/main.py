"""
PortfolioNarrator — FastAPI app entry.

The CORSMiddleware MUST be added before any route inclusions.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

# ─── Static files (fonts, templates) ───
app.mount("/static", StaticFiles(directory="static"), name="static")

# ─── Routers ───
from routes import admin, auth, clients, config, jobs, reports  # noqa: E402

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(clients.router, prefix="/clients", tags=["Clients"])
app.include_router(reports.router, prefix="/reports", tags=["Reports"])
app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(config.router, prefix="/config", tags=["Config"])


@app.get("/health", tags=["Health"])
async def health() -> dict[str, str]:
    """Lightweight health check — used by EasyCron keep-alive."""
    return {"status": "ok"}
