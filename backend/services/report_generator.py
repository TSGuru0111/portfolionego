"""Cohere streaming + QA pipeline — Day 6.

End-to-end flow for one client's monthly letter:

  1. ``context_builder.build_context_packet`` (called by the route)
  2. ``prompt_builder.validate / build_prompt_safe`` here
  3. Cohere ``chat_stream`` → ``command-r-plus`` → yield text chunks
  4. After the stream closes → ``run_qa_check`` → score 1-10
  5. If score < 7 → ``regenerate_strict`` (non-streamed, returns full text)
  6. ``reports_db.save_report`` → persist final text + score
  7. Append a JSON meta trailer (``[[META]]…[[END]]``) so the frontend
     learns ``report_id`` + ``qa_score`` without a second round-trip.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, AsyncGenerator

import cohere

from db import reports_db
from services import prompt_builder
from services.error_logger import log_error

GENERATION_MODEL = "command-r-plus-08-2024"
QA_MODEL = "command-r-08-2024"
QA_THRESHOLD = 7

# Meta trailer sentinels — chosen to be very unlikely in real letter text.
META_OPEN = "\n\n[[META]]"
META_CLOSE = "[[END]]"

_QA_PROMPT = (
    "You are a strict QA reviewer for an Indian wealth-management RM "
    "letter. Score the letter below from 1 (template slop) to 10 "
    "(indistinguishable from a senior RM). Penalise heavily: generic "
    "phrases, missing client numbers, missing ticker attribution, "
    "factual contradictions with the context, banned phrases. Respond "
    "with ONLY a JSON object: {\"score\": <int 1-10>, \"reasons\": "
    "[\"...\", \"...\"]}.\n\nLETTER:\n"
)


# ──────────────────────────────────────────────── Cohere client ──

def _cohere_client() -> cohere.Client | None:
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        return None
    return cohere.Client(api_key=api_key)


# ──────────────────────────────────────────────── QA scoring ──

def _extract_score(raw: str) -> int:
    """Parse Cohere's QA reply into an int score; defensive fallback."""
    if not raw:
        return 0
    # Try strict JSON first.
    try:
        payload = json.loads(raw)
        score = int(payload.get("score", 0))
        return max(0, min(10, score))
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    # Fall back to first integer in the text.
    m = re.search(r"\b(10|[1-9])\b", raw)
    return int(m.group(1)) if m else 0


def _qa_blocking(client: cohere.Client, letter_text: str) -> int:
    resp = client.chat(
        model=QA_MODEL,
        message=_QA_PROMPT + letter_text[:8000],
        temperature=0.1,
        max_tokens=120,
    )
    return _extract_score(getattr(resp, "text", "") or "")


async def run_qa_check(letter_text: str) -> int:
    """Score the letter 1-10. Returns 0 if Cohere is unavailable."""
    client = _cohere_client()
    if client is None or not letter_text.strip():
        return 0
    try:
        return await asyncio.to_thread(_qa_blocking, client, letter_text)
    except Exception as exc:  # noqa: BLE001
        await log_error("qa_check", exc)
        return 0


# ──────────────────────────────────────────────── regenerate ──

def _regen_blocking(client: cohere.Client, prompt: str) -> str:
    resp = client.chat(
        model=GENERATION_MODEL,
        message=prompt,
        temperature=0.6,
        max_tokens=1800,
    )
    return (getattr(resp, "text", "") or "").strip()


async def regenerate_strict(
    context: dict[str, Any],
    original_score: int,
) -> str:
    """Non-streamed strict regeneration. Returns full text."""
    client = _cohere_client()
    if client is None:
        return ""
    note = (
        f"Previous draft scored {original_score}/10. Tighten every "
        "section, add more specific numbers, and remove any generic "
        "sentences."
    )
    prompt = prompt_builder.build_strict_prompt(context, note=note)
    return await asyncio.to_thread(_regen_blocking, client, prompt)


# ──────────────────────────────────────────────── streaming ──

async def _stream_letter(
    client: cohere.Client,
    prompt: str,
) -> AsyncGenerator[str, None]:
    """Adapt the synchronous Cohere ``chat_stream`` iterator to async.

    We run the blocking iterator in a thread and bridge each chunk back
    through ``asyncio.Queue``.
    """
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def _drain() -> None:
        try:
            for event in client.chat_stream(
                model=GENERATION_MODEL,
                message=prompt,
                temperature=0.7,
                max_tokens=1800,
            ):
                # cohere 5.x: events are typed; text-generation events
                # carry ``text``. Be defensive across SDK minor versions.
                etype = getattr(event, "event_type", None) or getattr(
                    event, "type", None
                )
                if etype == "text-generation":
                    text = getattr(event, "text", None) or ""
                    if text:
                        loop.call_soon_threadsafe(queue.put_nowait, text)
                elif etype == "stream-end":
                    break
        except Exception as exc:  # noqa: BLE001
            loop.call_soon_threadsafe(
                queue.put_nowait, f"\n\n[stream error: {exc}]"
            )
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    fut = loop.run_in_executor(None, _drain)
    try:
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk
    finally:
        await fut


# ──────────────────────────────────────────────── public pipeline ──

async def generate_report_stream(
    client_id: str,
    month: str,
    context: dict[str, Any],
) -> AsyncGenerator[str, None]:
    """End-to-end streaming pipeline.

    Yields letter-text chunks as Cohere emits them, then on completion
    runs QA + (optionally) regenerates, saves to Supabase, and yields a
    final META trailer the frontend strips before display.
    """
    client = _cohere_client()
    if client is None:
        yield "Cohere API key not configured — set COHERE_API_KEY."
        yield (
            f"{META_OPEN}"
            + json.dumps({"report_id": None, "qa_score": 0, "error": "no_api_key"})
            + META_CLOSE
        )
        return

    prompt = prompt_builder.build_prompt_safe(context, strict=False)
    streamed = ""

    try:
        async for chunk in _stream_letter(client, prompt):
            streamed += chunk
            yield chunk
    except Exception as exc:  # noqa: BLE001
        await log_error("report_generator.stream", exc, {"client_id": client_id})
        yield f"\n\n[generation failed: {exc}]"

    final_text = streamed.strip()
    qa_score = await run_qa_check(final_text) if final_text else 0

    if final_text and qa_score and qa_score < QA_THRESHOLD:
        try:
            regenerated = await regenerate_strict(context, qa_score)
            if regenerated:
                final_text = regenerated
                qa_score = await run_qa_check(final_text)
                # Emit the regenerated text as a single visible "redraft"
                # block so the user can see we re-wrote it.
                yield "\n\n— Redrafted for tone and specificity —\n\n"
                yield regenerated
        except Exception as exc:  # noqa: BLE001
            await log_error("report_generator.regen", exc, {"client_id": client_id})

    report_id: str | None = None
    if final_text:
        try:
            report_id = await reports_db.save_report(
                client_id=client_id,
                month=month,
                generated_text=final_text,
                qa_score=qa_score,
            )
        except Exception as exc:  # noqa: BLE001
            await log_error(
                "report_generator.save", exc, {"client_id": client_id}
            )

    yield (
        f"{META_OPEN}"
        + json.dumps({"report_id": report_id, "qa_score": qa_score})
        + META_CLOSE
    )
