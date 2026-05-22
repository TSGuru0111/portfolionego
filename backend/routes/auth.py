"""Auth routes.

Supabase Auth runs in the browser; the backend only needs to verify the
JWT and provide a logout convenience endpoint.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.post("/logout")
async def logout() -> dict[str, str]:
    """Stateless logout — frontend clears its session, this is a no-op."""
    return {"status": "ok"}
