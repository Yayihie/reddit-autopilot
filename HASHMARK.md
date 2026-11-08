# Hashmark setup (draft-only)

Reviewed setup for Hashmark on this repo. **Live Reddit sends are off.**
Automatic posting is not activated here. Any later unattended send must come
from a parent-managed saved routine, not from a loop launched in this
environment.

PWG (Pace With Grace) keeps the default home `~/.reddit-autopilot`. Hashmark
must always pass `--profile hashmark` or `RAP_PROFILE=hashmark`.

This environment does **not** have the parent-desktop Reddit session. Do not
copy cookies, tokens, or CDP debug ports from that machine.

## What this repo actually does

Source of truth: `src/reddit_autopilot/`.

| Piece | Module | Side effects |
|---|---|---|
| Config / queue | `config.py`, `queue.py` | Local JSON + SQLite under the profile home. No Reddit. |
| Policy | `policy.py` | Local `policy-state.json`. Hashmark extra rules in `brand.py`. |
| plan / compare / draft | `planner.py` → `reddit-growth` CLI | **Network.** Default path is Arctic Shift (`https://arctic-shift.photon-reddit.com`), not a post. If `REDDIT_CLIENT_ID` is set, [reddit-growth-mcp](https://github.com/latent-9/reddit-growth-mcp) uses PRAW against **live Reddit (read)**. Hashmark default `allow_network_planning=false` blocks these commands. |
| Warm-up sweep | `warmup.fetch_recent` | HTTP GET to Arctic Shift. Not a Reddit write; still network. Blocked on Hashmark. |
| Dry-run `post` / `comment` / `run` | `cli.py`, `scheduler.py` | Local only after this change. Must not call `whoami` / `get_session`. A URL in a text body counts as a linked action. |
| `--live` post/comment/run | `reddit_api.py` | Writes via a logged-in browser: CDP (`browser_cdp.py`) or AppleScript (`browser.py`) injecting `fetch()` to **undocumented `www.reddit.com/api/*`** (`/api/submit`, `/api/comment`, `/api/vote`, `/api/me.json`) with cookies + **modhash**. Not OAuth. |
| `login` / `health` / `verify` / `warmup ready` | `health.py`, `verify.py` | Session reads through that same browser backend. Blocked on Hashmark. |
| `browser launch` | `browser_cdp.py` | Starts Chrome with `--remote-debugging-port` (default 9222) and a dedicated profile dir. Blocked on Hashmark. |
| `scripts/run_forever.sh` | bash loop | Now defaults to dry-run. `LIVE=1` + `RAP_PROFILE=hashmark` exits 1. |

`RULES.md` previously claimed the tool never votes. That is false for the
default tree: `reddit_api.vote` and `warmup.upvote_recent` exist (commit
`5ef4e95`). Hashmark forbids votes in `brand.py` and `activation.py`.

## Current backend vs documented supported route

**This repo's live backend is not a supported Hashmark activation path.**

It drives Chrome over CDP or AppleScript, then same-origin `fetch` of Reddit's
web `/api/*` endpoints with the browser cookie jar and modhash. README and
CREDITS.md describe this as intentional ("no Reddit API keys required").

Do **not** activate Hashmark by:

- copying cookies or tokens from the parent desktop
- attaching to that Chrome via CDP / DevTools
- scripting a logged-in browser
- calling undocumented `www.reddit.com/api/*` from this process

**Documented supported route** (not implemented here; this source does not
grant API access):

1. Reddit OAuth2: <https://github.com/reddit-archive/reddit/wiki/OAuth2>
2. App types: <https://github.com/reddit-archive/reddit/wiki/OAuth2-App-Types>
3. Create an app only if Reddit still issues you one (prefs → apps /
   [developer platform](https://developers.reddit.com/app-registration)).
   Self-service Data API access has been restricted; **do not invent
   permission**. Registering an app is an operator action, not something this
   repo can do.
4. Authorized calls go to `oauth.reddit.com` with a bearer token and requested
   scopes (`submit`, `identity`, …) — not cookie/modhash `www.reddit.com/api/*`.

Until an OAuth client exists **and** a parent-managed saved routine names the
exact posting behavior, Hashmark `activation_blocked` stays true.

## Manual review boundary

Allowed now (local, no Reddit):

```bash
rap --profile hashmark profile
rap --profile hashmark doctor          # no --with-browser
rap --profile hashmark config init
rap --profile hashmark config show
rap --profile hashmark policy
rap --profile hashmark warmup plan
rap --profile hashmark post <sub> --title "..." --text "..."          # dry-run
rap --profile hashmark comment t3_example --text "..."                # dry-run
rap --profile hashmark schedule ...
rap --profile hashmark queue list
rap --profile hashmark run             # dry-run; does not mark items done
```

Blocked on Hashmark (even with `--live`):

- `post --live`, `comment --live`, `run --live`, `warmup comment --live`
- `login`, `health`, `verify`, `open-tab`, `browser launch`, `warmup sweep`, `warmup ready`
- `plan` / `compare` / `draft` until `allow_network_planning` is explicitly true
- votes, unattended `LIVE=1` loops
- any send before `2026-11-09T00:00:00-08:00`

Queueing a draft is not permission to send it. `run --live` is refused. A
future parent-managed saved routine has to authorize specific posting
behavior; this process will not launch that loop.

## Hashmark facts (promotion)

Only these product facts:

- Site: `https://playhashmark.com`
- `/football` — The Cut Line, weekly lowest-score elimination
- `/basketball` — NBA Monthly Gauntlet, monthly elimination
- Free, no buy-in, credits only
- Disclose: `I'm on the Hashmark team`

Forbidden in `brand.py` (not a complete English parser; these are substring
guards): guillotine; buy-in / entry fee / cash / real-money H2H; eliminated
roster → waivers; commissioning a league; invented first-person experience
lines from the generic warm-up bank.

Do not invent league size or settings. Do not promote in crisis threads
(existing `CRISIS_KEYWORDS`). Promotion must be relevant and allowed by that
subreddit's rules. Cadence: at most one linked Reddit action per day; the same
URL at most one subreddit per day. No Reddit until Monday 9 Nov 2026 PT.

Target subreddits are **empty on purpose**. Do not copy PWG's Christian list.

## Exact safe setup commands

From a clone, **offline**, no Reddit, no extra spend:

```bash
# isolated home (do not use the default ~/.reddit-autopilot PWG dir)
export RAP_PROFILE=hashmark

# stdlib core + test extras only — do not install [cdp], [growth], or [bridge]
uv venv
uv pip install -e ".[dev]"
uv run pytest -q
uv run ruff check src tests

rap --profile hashmark profile
rap --profile hashmark config init
rap --profile hashmark doctor
rap --profile hashmark policy
```

Do **not** run: `rap login`, `rap browser launch`, `pip install 'reddit-autopilot[cdp]'`,
`LIVE=1 bash scripts/run_forever.sh`, or anything with `--live` for Hashmark.

Optional later (operator machine, still not this agent): enable
`allow_network_planning` only if you accept Arctic Shift HTTP and you have
**not** set `REDDIT_CLIENT_ID`. That still does not authorize posting.

## Isolation

| | PWG (default) | Hashmark |
|---|---|---|
| Env | unset `RAP_PROFILE` | `RAP_PROFILE=hashmark` |
| Home | `~/.reddit-autopilot` | `~/.reddit-autopilot/profiles/hashmark` |
| Queue / policy / chrome-profile | existing files, not modified by Hashmark commands | separate paths |
| `--live` | previous behavior (browser backend) | blocked |
| Votes | code still present | blocked |

`REDDIT_AUTOPILOT_HOME` overrides both. Tests use that override.

## Remaining blockers (not done)

1. No official OAuth posting client in this repo.
2. Reddit API app registration / approval is an operator action; this source
   cannot expand authorization. Self-service access may be closed.
3. No Hashmark subreddit allowlist (must be chosen against each sub's rules).
4. No parent-managed saved routine exists in this run; unattended posting is
   not configured.
5. `plan`/`compare`/`draft` are gated off on Hashmark; they were not executed
   here (Arctic / optional Reddit).
6. This Cloud Agent did not install Chrome, did not log into Reddit, and did
   not verify a live session. **Do not report Hashmark Reddit operations as
   live.**
7. Default/PWG still has CDP + vote code. This PR does not remove it.

## Completed in this PR

- Source-grounded review of scripts, deps, tests, live vs dry-run, session
  handling, and security.
- Isolated Hashmark profile template + content/activation gates.
- Dry-run `post`/`comment` no longer call `whoami`.
- `run_forever.sh` defaults to dry-run; Hashmark `LIVE=1` refused.
- Offline tests for isolation, live-send block, disclosure, forbidden claims,
  vote block, and dry-run session avoidance.
