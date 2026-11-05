"""Content helpers: comment bank, warm-up comment generator, human-timing jitter."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

# Value-first comment starters used during account warm-up. These are the kind
# of comments that build karma safely: genuinely helpful, no links, no product
# mentions. Swap in your own per-niche bank for best results.
WARMUP_COMMENT_BANK = [
    "This matches my experience — the part about {topic} was the bit that finally clicked for me.",
    "Good write-up. One thing that helped me was simplifying first and adding complexity only when it hurt.",
    "Curious what you'd do differently if you had to start over? I'm about to tackle {topic} myself.",
    "Saving this. The {topic} section is underrated — most guides skip straight past it.",
    "Thanks for sharing real numbers instead of vibes. Did you measure this over a week or longer?",
    "Honestly the hard part for me wasn't the tooling, it was deciding what to ignore. {topic} being a good example.",
    "This is the clearest explanation of {topic} I've seen on here. Bookmarking for later.",
    "Strongly agree. I'd add that consistency mattered way more than any single tweak for me.",
]

# Optional soft sign-offs you can enable per subreddit where self-mention is allowed
# *and disclosed*. Left empty on purpose so nothing promotional ships by default.
DISCLOSED_PROMO_TEMPLATE = (
    "Disclosure: I build a tool in this space. {value} — happy to share if it's useful, no pressure."
)


def human_jitter(base_minutes: int, spread: float = 0.4) -> timedelta:
    """Return a randomised delay around base_minutes — never act on a fixed cadence."""
    jitter = random.uniform(-spread, spread) * base_minutes
    return timedelta(minutes=max(1.0, base_minutes + jitter))


def warmup_comments(per_day: int, topics: list[str] | None = None) -> list[str]:
    topics = topics or ["getting started", "picking the right tool", "scaling up"]
    picks = random.sample(WARMUP_COMMENT_BANK, k=min(per_day, len(WARMUP_COMMENT_BANK)))
    out = []
    for c in picks:
        out.append(c.format(topic=random.choice(topics)))
    return out


def next_slots(count: int, start: datetime | None = None, spacing_minutes: int = 90) -> list[datetime]:
    start = start or datetime.now(timezone.utc)
    slots = []
    t = start
    for _ in range(count):
        t = t + human_jitter(spacing_minutes)
        slots.append(t)
    return slots


def disclosure_comment(value_prop: str) -> str:
    return DISCLOSED_PROMO_TEMPLATE.format(value=value_prop)
