"""Prompt builder.

Day 1-2: scaffolding only.
Day 3 (now): hooks for config-driven system context + style samples so the
Config tab can influence generation today, without waiting for Day 5's
hand-written few-shot letters.

Day 5 will lock down ``build_prompt_safe()`` with the final structure.
"""
from __future__ import annotations

from typing import Any

from services import config_store

BANNED_PHRASES: list[str] = [
    "market volatility",
    "challenging environment",
    "headwinds",
    "uncertain times",
    "it is worth noting",
    "needless to say",
    "going forward",
    "at this juncture",
    "in this regard",
]

# Placeholder slots — replaced with hand-written letters on Day 5.
FEW_SHOT_LETTER_A: str = ""
FEW_SHOT_LETTER_B: str = ""


def load_system_context() -> str:
    """Concatenated content of every ``backend/config/agents/*.md`` file.

    Called by the report generator on each request so edits in the Config
    tab take effect immediately, without restarting the process.
    """
    return config_store.read_all_agent_context()


def load_style_samples(limit: int | None = None) -> list[str]:
    """Return uploaded RM letters from ``backend/config/style_samples/``."""
    samples = config_store.read_all_style_samples()
    if limit is not None:
        return samples[:limit]
    return samples


def build_prompt_safe(context: dict[str, Any], strict: bool = False) -> str:
    """TODO(Day 5): build production prompt with few-shot + context.

    Day 5 will combine:
      - ``load_system_context()`` — house view + persona + rules
      - ``load_style_samples()`` — prior RM letters as few-shot examples
      - ``FEW_SHOT_LETTER_A`` / ``FEW_SHOT_LETTER_B`` — hand-written anchors
      - ``BANNED_PHRASES`` — negative constraints
      - ``context`` — portfolio + market + news packet
    """
    raise NotImplementedError("prompt_builder.build_prompt_safe — Day 5")


def build_strict_prompt(context: dict[str, Any], note: str = "") -> str:
    """TODO(Day 5): regenerate-with-stricter-prompt variant."""
    raise NotImplementedError("prompt_builder.build_strict_prompt — Day 5")
