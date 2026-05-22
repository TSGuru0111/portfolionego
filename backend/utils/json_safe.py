"""Safe JSON parsing for LLM output.

Cohere occasionally returns JSON wrapped in markdown fences or with
preamble text. ``safe_parse_json`` strips fences, extracts the first
JSON object found, and returns safe defaults on failure — it never
raises, so the pipeline cannot crash on malformed output.
"""
from __future__ import annotations

import json
import re
from typing import Any

_DEFAULTS: dict[str, Any] = {
    "score": 8,
    "weakest_section": None,
    "reason": "json_parse_error",
}


def safe_parse_json(raw: str) -> dict[str, Any]:
    if not raw or not isinstance(raw, str):
        return dict(_DEFAULTS)

    cleaned = re.sub(r"```json|```", "", raw).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        return dict(_DEFAULTS)
    except (json.JSONDecodeError, ValueError):
        return dict(_DEFAULTS)
