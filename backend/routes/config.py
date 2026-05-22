"""Config tab endpoints.

Anyone logged in (any valid Supabase session at the frontend) can edit.
No backend session check yet — matches the rest of the app's current
posture. Lock down later via a Bearer token + ``supabase.auth.get_user``.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from services import config_store

router = APIRouter()


# ---------------------------------------------------------------- agents ----

class AgentFilePayload(BaseModel):
    content: str


@router.get("/agents")
async def list_agents() -> list[dict[str, Any]]:
    return config_store.list_agent_files()


@router.get("/agents/{name}")
async def get_agent(name: str) -> dict[str, Any]:
    try:
        return {"name": name, "content": config_store.read_agent_file(name)}
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/agents/{name}")
async def put_agent(name: str, payload: AgentFilePayload) -> dict[str, Any]:
    try:
        return config_store.write_agent_file(name, payload.content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/agents/{name}")
async def delete_agent(name: str) -> dict[str, str]:
    try:
        config_store.delete_agent_file(name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"status": "ok"}


# ----------------------------------------------------------------- feeds ----

@router.get("/feeds")
async def get_feeds() -> dict[str, Any]:
    return config_store.read_feeds()


@router.put("/feeds")
async def put_feeds(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return config_store.write_feeds(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


# ---------------------------------------------------------- style samples ----

class StyleSamplePayload(BaseModel):
    content: str
    title: str | None = None


@router.get("/style-samples")
async def list_style_samples() -> list[dict[str, Any]]:
    return config_store.list_style_samples()


@router.get("/style-samples/{sample_id}")
async def get_style_sample(sample_id: str) -> dict[str, Any]:
    try:
        return {
            "id": sample_id,
            "content": config_store.read_style_sample(sample_id),
        }
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/style-samples")
async def create_style_sample(payload: StyleSamplePayload) -> dict[str, Any]:
    if not payload.content.strip():
        raise HTTPException(400, "Empty sample content")
    return config_store.create_style_sample(payload.content, payload.title)


@router.delete("/style-samples/{sample_id}")
async def delete_style_sample(sample_id: str) -> dict[str, str]:
    try:
        config_store.delete_style_sample(sample_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"status": "ok"}
