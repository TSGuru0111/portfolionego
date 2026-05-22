"""Cheap token estimator (4 chars ≈ 1 token).

Avoids importing tiktoken on every call. Accurate to within ~15% for
English + Hindi mixed text and is more than enough for context trimming
decisions.
"""
from __future__ import annotations


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def fits_within(text: str, max_tokens: int) -> bool:
    return estimate_tokens(text) <= max_tokens
