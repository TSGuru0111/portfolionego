"""Prompt builder — Day 5 (locked).

Assembles the final Cohere Command R+ prompt for one client's monthly
letter. Returns a single string so the report_generator can feed it as
the ``message`` argument to ``co.chat()`` / ``co.chat_stream()``.

Structure of the returned prompt:

  [SYSTEM]              — persona, house view, hard rules (from Config tab)
  [BANNED PHRASES]      — negative constraints
  [LETTER STRUCTURE]    — 7-section spec
  [EXAMPLE LETTERS]     — two hand-written anchors (FEW_SHOT_LETTER_A/B)
  [STYLE SAMPLES]       — uploaded prior-RM letters (optional, from Config)
  [CONTEXT PACKET]      — JSON dump of build_context_packet output
  [TASK]                — final instruction; strict mode tightens it

After today this file is **locked** — no more prompt edits without a
matching change to the few-shot letters.
"""
from __future__ import annotations

import json
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

LETTER_STRUCTURE: str = (
    "1. Personal opening — reference the last meeting if notes exist.\n"
    "2. Market snapshot — Nifty 1-month return, sectors, macro in 3-4 lines.\n"
    "3. Portfolio performance — client's numbers vs. Nifty, with named-"
    "stock attribution. If a rationale_trade exists, reference it by ticker.\n"
    "4. Sector commentary — only sectors the client actually holds.\n"
    "5. Honest assessment — name the underperformers and what we're "
    "watching. If any prices are stale (source != 'live'), call this out.\n"
    "6. Forward view — house stance + how it affects this portfolio.\n"
    "7. Call to action — propose a date for the next review.\n"
)

# ────────────────────────────────────────────────── few-shot anchors ──
# Hand-written 22 Oct 2025. These are the tonal anchors for every letter.
# Any future edit MUST come with a paired review of generated output.

FEW_SHOT_LETTER_A: str = """Dear Vikram,

Thank you for the conversation last Thursday — I have noted your interest in adding a second debt allocation once we cross the next ₹25 lakh of accruals. This letter covers the period ending 30 September 2025.

Markets — Nifty 50 closed the month up 1.3%, with IT services and select private banks doing most of the heavy lifting. The Rupee weakened 0.6% against the Dollar, which quietly tailwinds your IT exposure, and Brent traded in a tight ₹83-87 range with no surprises from the RBI in its September review.

Performance — Your portfolio of ₹1.85 Cr returned 2.8% over the month, ahead of Nifty by 1.5%. TCS led the table with an 8.0% gain after a clean Q2 print and a stronger-than-expected deal TCV of $11.2 bn; Infosys added 4.2% on the upgraded FY26 guidance, and HCL Technologies put up 5.5% on the ER&D segment commentary. The additional TCS lot we picked up on 14 August — "added on IT dip; deal pipeline holding firm" was your note from that call — is now sitting on a 9.6% return.

Sectors you own — IT services contributed almost the entire month's outperformance. Private banks (HDFC Bank, ICICI Bank) were broadly flat; the credit-cost commentary at the HDFC Bank investor day was reassuring without being thrilling. Your single auto-name (Maruti Suzuki) gained 1.1%, in line with the index.

Honest read — The portfolio's IT weight is now 57%, up from your target band of 45-55%. That bias paid off this month but it is a concentration we should address before the next earnings season. Your two laggards are Tata Steel (-2.3%, China steel-export pricing) and Asian Paints (-1.4%, raw-material pass-through still incomplete). Neither is a thesis break in my view.

What we expect — Our house view is that IT services have one more quarter of relative strength before the discretionary-spend conversation reasserts itself in Q4 FY26. We would prefer to lighten your IT exposure by 5-6 percentage points and rotate into a domestic-consumption name on any meaningful pullback — Trent or Titan are the two on the shortlist.

Next step — I would like to do a 30-minute review on the IT rebalance and the second debt tranche around the second week of October. I will send three slots tomorrow.

Warm regards,

Priya Menon
Senior Relationship Manager, Wealth Advisory Group
priya.menon@example.com  ·  +91 98XXX XX012
"""

FEW_SHOT_LETTER_B: str = """Dear Anil,

I hope the renovation work is wrapping up — you had mentioned the Diwali deadline when we last spoke. This note covers the month ending 31 August 2025.

Markets — Nifty 50 was up 1.3% for the month, but the index masked a sharp sector dispersion: IT services and private banks led, while pharma and FMCG lagged. The Rupee held steady at ₹83.4 against the Dollar, and the RBI left the repo rate at 6.50% in its August meeting — broadly in line with our base case.

Performance — Your portfolio of ₹1.20 Cr returned -0.7% over the month, trailing Nifty by 2.0%. The drag came almost entirely from pharma, which is 38% of your book. Sun Pharma fell 4.8% after the USFDA Form 483 observation on the Halol facility — a manufacturing-process flag rather than a product issue, and the company has guided to a 60-90 day remediation. Cipla was flat; Dr. Reddy's gave back 2.1% on a slower US generics print.

Sectors you own — Outside pharma, the read is mixed in your favour. ICICI Bank added 2.7% on the upgraded credit guidance; the SBI position contributed a steady 1.8%; Hindustan Unilever and Nestle India were both marginally positive, with the rural-volume commentary at HUL's quarterly call particularly encouraging.

Honest read — Two things to call out plainly. First, the Sun Pharma drawdown is uncomfortable but, on the data we have, it does not change our thesis — we are watching the remediation timeline closely. Second, our yfinance feed could not pull a live print for Cipla on the cut-off date, so the ₹1,478 we are using is the previous trading day's close — not a material issue, but worth flagging.

What we expect — Our house view is that pharma will see another month of relative weakness before US generic pricing stabilises in November. We do not recommend selling Sun Pharma at these levels; we do, however, recommend pausing the SIP-equivalent topup into Cipla until the next quarterly results, redirecting that allocation to your existing HDFC Banking & PSU Debt Fund position.

Next step — Could we meet in the first week of September to walk through the pharma re-underwriting note we are preparing? I will hold three afternoon slots for you.

Warm regards,

Rohit Bansal
Vice President, Private Wealth
rohit.bansal@example.com  ·  +91 98XXX XX045
"""


# ──────────────────────────────────────────────────── config loaders ──

def load_system_context() -> str:
    """Concatenated content of every ``backend/config/agents/*.md`` file."""
    return config_store.read_all_agent_context()


def load_style_samples(limit: int | None = None) -> list[str]:
    """Return uploaded RM letters from ``backend/config/style_samples/``."""
    samples = config_store.read_all_style_samples()
    if limit is not None:
        return samples[:limit]
    return samples


# ─────────────────────────────────────────────────── helpers ──

def _banned_phrases_block() -> str:
    return "\n".join(f"- '{p}'" for p in BANNED_PHRASES)


def _system_block(extra: str = "") -> str:
    cfg = load_system_context().strip()
    base = (
        "You are a senior Relationship Manager at an Indian private "
        "wealth firm with over 12 years of HNI relationship experience. "
        "You write monthly portfolio review letters that are personal, "
        "technically precise, and respect the client's time."
    )
    parts = [base]
    if cfg:
        parts.append("HOUSE GUIDELINES AND PERSONA (from Config tab):\n" + cfg)
    if extra:
        parts.append(extra)
    return "\n\n".join(parts)


def _examples_block(include_style_samples: bool = True) -> str:
    parts = [
        "--- EXAMPLE LETTER A — IT-heavy outperformer ---",
        FEW_SHOT_LETTER_A.strip(),
        "--- EXAMPLE LETTER B — Pharma-heavy underperformer ---",
        FEW_SHOT_LETTER_B.strip(),
    ]
    if include_style_samples:
        samples = load_style_samples(limit=2)
        for i, s in enumerate(samples, start=1):
            parts.append(f"--- STYLE SAMPLE {i} (prior RM letter, match the tone) ---")
            parts.append(s.strip())
    return "\n\n".join(parts)


def _serialise_context(context: dict[str, Any]) -> str:
    return json.dumps(context, default=str, ensure_ascii=False, indent=2)


def _task_block(strict: bool, note: str = "") -> str:
    base = (
        "Write the letter for the client described in the CONTEXT PACKET "
        "above. Follow the 7-section LETTER STRUCTURE.\n\n"
        "Rules:\n"
        "- 600-800 words.\n"
        "- Use Indian number formatting (₹X.XX Cr, 1,23,456).\n"
        "- Reference real numbers from the context — never invent figures.\n"
        "- Mention each top performer and underperformer by ticker.\n"
        "- If `rationale_trades` is non-empty, reference at least one by "
        "ticker and quote the rationale text.\n"
        "- If `has_stale_prices` is true, mention this explicitly in "
        "Section 5 and name the stale tickers.\n"
        "- Sign off with the RM name from the context — never invent.\n"
        "- Do NOT use any of the BANNED PHRASES listed above.\n"
        "- Do NOT add disclaimers — the PDF template appends one.\n"
        '- Start the letter with "Dear {first name},"\n'
    )
    if strict:
        base += (
            "\nSTRICT MODE — the previous draft was rejected by QA. Be "
            "more specific with numbers, cut every generic sentence, and "
            "make sure each of the 7 sections is clearly present."
        )
    if note:
        base += f"\n\nReviewer note: {note.strip()}"
    return base


# ─────────────────────────────────────────────────── public API ──

def build_prompt_safe(context: dict[str, Any], strict: bool = False) -> str:
    """Build the production prompt for ``co.chat()`` / ``co.chat_stream()``.

    The full string is intended as the ``message`` argument; the report
    generator may optionally lift the SYSTEM block into ``preamble`` —
    the structure tolerates either approach.
    """
    blocks = [
        "[SYSTEM]",
        _system_block(),
        "[BANNED PHRASES — never use any of these, even reworded]",
        _banned_phrases_block(),
        "[LETTER STRUCTURE]",
        LETTER_STRUCTURE,
        "[EXAMPLE LETTERS]",
        _examples_block(include_style_samples=True),
        "[CONTEXT PACKET]",
        _serialise_context(context),
        "[TASK]",
        _task_block(strict=strict),
    ]
    return "\n\n".join(blocks)


def build_strict_prompt(context: dict[str, Any], note: str = "") -> str:
    """Regenerate variant — fires when QA score < 7 on the first draft."""
    blocks = [
        "[SYSTEM]",
        _system_block(),
        "[BANNED PHRASES — never use any of these, even reworded]",
        _banned_phrases_block(),
        "[LETTER STRUCTURE]",
        LETTER_STRUCTURE,
        "[EXAMPLE LETTERS]",
        _examples_block(include_style_samples=False),
        "[CONTEXT PACKET]",
        _serialise_context(context),
        "[TASK]",
        _task_block(strict=True, note=note),
    ]
    return "\n\n".join(blocks)
