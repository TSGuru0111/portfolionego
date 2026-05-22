"""Cohere streaming + QA pipeline — stub for Day 1-2.

Real implementation arrives on Day 6 (after prompt locks on Day 5).
"""
from __future__ import annotations

from typing import Any, AsyncGenerator


async def generate_report_stream(
    client_id: str,
    context: dict[str, Any],
) -> AsyncGenerator[str, None]:
    """TODO(Day 6): Cohere streaming + post-stream QA check."""
    raise NotImplementedError(
        "report_generator.generate_report_stream — Day 6"
    )
    # Unreachable — required so Python recognises this as a generator.
    yield ""  # pragma: no cover


async def run_qa_check(letter_text: str) -> int:
    """TODO(Day 6): Cohere QA scoring 1-10."""
    raise NotImplementedError("report_generator.run_qa_check — Day 6")


async def regenerate_strict(context: dict[str, Any], original_score: int) -> str:
    """TODO(Day 6): regenerate with stricter prompt when score < 7."""
    raise NotImplementedError("report_generator.regenerate_strict — Day 6")
