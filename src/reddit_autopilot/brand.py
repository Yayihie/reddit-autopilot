"""Brand-specific content rules.

Hashmark facts are the committed profile plus the operators' explicit claims
list. Public marketing copy is not extra authorization: if a claim is forbidden
here, it stays forbidden even if playhashmark.com currently says something else.
"""

from __future__ import annotations

from urllib.parse import urlparse

from reddit_autopilot.config import Config, profile_name

HASHMARK_DISCLOSURE = "I'm on the Hashmark team"
HASHMARK_ALLOWED_HOSTS = {"playhashmark.com"}

# Lowest-score elimination formats, free play, credits only. Do not add league
# size, commissioning, cash, or "guillotine" language.
HASHMARK_ALLOWED_CLAIMS = (
    "playhashmark.com",
    "/football live The Cut Line (weekly lowest-score elimination)",
    "/basketball NBA Monthly Gauntlet (monthly elimination)",
    "Free, no buy-in, credits only",
    "Disclose: I'm on the Hashmark team",
)

# Substrings matched case-insensitively in titles, bodies, and URLs.
HASHMARK_FORBIDDEN_PHRASES = (
    "guillotine",
    "buy-in",
    "buy in",
    "buyin",
    "entry fee",
    "cash prize",
    "cash for trade",
    "cash-for-trade",
    "real-money",
    "real money",
    "h2h cash",
    "head-to-head cash",
    "head to head cash",
    "eliminated roster",
    "roster hits the waiver",
    "roster goes to waivers",
    "roster to waivers",
    "roster enters the waiver",
    "commissioned a league",
    "i commissioned",
    "we commissioned",
)

# First-person filler from the generic warm-up bank. Hashmark must not invent
# personal experiences.
HASHMARK_FAKE_EXPERIENCE_PHRASES = (
    "matches my experience",
    "the bit that finally clicked for me",
    "one thing that helped me",
    "i'm about to tackle",
    "the hard part for me",
    "i've seen on here",
    "mattered way more than any single tweak for me",
)

HASHMARK_WARMUP_BANK = (
    "Which scoring format does this league use for flex, and why that one over PPR?",
    "How do you handle weekly lineup lock vs daily lock when players sit out late?",
    "What's a fair FAAB bid range on a replacement-level starter this week?",
    "Is lowest-score elimination a better fit than head-to-head for a casual group?",
    "When a format is free with credits only, what still makes the weekly decision interesting?",
)


def is_hashmark(cfg: Config | None = None) -> bool:
    if profile_name() == "hashmark":
        return True
    cfg = cfg or Config.load()
    return cfg.brand == "hashmark"


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _forbidden_phrase(blob: str, phrase: str) -> bool:
    """True when the forbidden phrase is claimed, not negated (e.g. 'no buy-in')."""
    if phrase not in blob:
        return False
    for neg in (f"no {phrase}", f"without {phrase}", f"without a {phrase}", f"zero {phrase}"):
        if neg in blob:
            return False
    return True


def _blob(texts: list[str] | None, url: str | None) -> str:
    parts = [t or "" for t in (texts or [])]
    if url:
        parts.append(url)
    return " ".join(parts).lower()


def check(
    kind: str,
    sub: str | None,
    *,
    link: bool = False,
    url: str | None = None,
    texts: list[str] | None = None,
    cfg: Config | None = None,
) -> dict:
    """Return {'ok', 'hard', 'soft'} extra brand rules. No-op when not Hashmark."""
    cfg = cfg or Config.load()
    if not is_hashmark(cfg):
        return {"ok": True, "hard": [], "soft": []}

    hard: list[str] = []
    soft: list[str] = []
    blob = _blob(texts, url)
    disclosure = str(cfg.get("disclosure") or HASHMARK_DISCLOSURE).lower()

    if kind == "vote":
        hard.append("Hashmark forbids votes, including warm-up upvotes")

    for phrase in HASHMARK_FORBIDDEN_PHRASES:
        if _forbidden_phrase(blob, phrase):
            hard.append(f"Hashmark forbidden claim: {phrase!r}")

    for phrase in HASHMARK_FAKE_EXPERIENCE_PHRASES:
        if phrase in blob:
            hard.append(f"Hashmark forbids invented personal experience ({phrase!r})")

    promotional = bool(link or (url and _host(url) in HASHMARK_ALLOWED_HOSTS) or "playhashmark.com" in blob)
    if promotional:
        if disclosure not in blob and "i am on the hashmark team" not in blob:
            hard.append(f"Hashmark promotional text must disclose: {cfg.get('disclosure') or HASHMARK_DISCLOSURE}")
        if url:
            host = _host(url)
            if host not in HASHMARK_ALLOWED_HOSTS:
                hard.append("Hashmark links must use https://playhashmark.com (no other hosts)")

    if kind in {"submit_link", "submit_text", "comment"} and sub is None and kind != "comment":
        hard.append("Hashmark posts need an explicit subreddit; do not invent a target list")

    return {"ok": not hard, "hard": hard, "soft": soft}
