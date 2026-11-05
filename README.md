# reddit-autopilot

An all-in-one, self-hosted Reddit growth system: **plan where to post → warm up
the account → schedule → act through your real browser session.** It stitches the
best current open-source Reddit tooling into one CLI, with a zero-dependency core
and **no Reddit API keys required.**

```
  ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐
  │   plan     │ → │  warm up   │ → │  schedule  │ → │    act     │
  │ (growth-   │   │ (7-day no- │   │  (SQLite   │   │ (AppleScript│
  │  mcp CLI)  │   │  link rite)│   │   queue)   │   │  → Chrome) │
  └────────────┘   └────────────┘   └────────────┘   └────────────┘
```

## Why browser-session automation?

Reddit's 2023 API pricing broke most API-based tooling, and Playwright/Selenium
set `navigator.webdriver = true` (instantly detectable). reddit-autopilot instead
drives **your real, logged-in Chrome** via AppleScript and Reddit's own internal
`/api/*` endpoints — the same technique the leading 2026 skills use. Cookies and
browser fingerprint are authentic; there is no API app to register.

## Install

```bash
# core (stdlib only)
pip install git+https://github.com/Yayihie/reddit-autopilot.git

# with the planning engine (recommended)
pip install "reddit-autopilot[growth] @ git+https://github.com/Yayihie/reddit-autopilot.git"
```

Or with uv:

```bash
uv tool install git+https://github.com/Yayihie/reddit-autopilot.git
uv tool install --with reddit-growth-mcp "reddit-autopilot @ git+https://github.com/Yayihie/reddit-autopilot.git"
```

## Backends

The action layer can drive Reddit two ways; it auto-selects:

| Backend | What it needs | Notes |
|---|---|---|
| **CDP** (recommended) | `rap browser launch` — an isolated Chrome on port 9222 | No permissions, no settings. `pip install 'reddit-autopilot[cdp]'` |
| **AppleScript** | macOS + Chrome with `View → Developer → Allow JavaScript from Apple Events` on | Works, but that setting cannot be enabled by any script — you must tick it yourself |

For CDP: `rap browser launch`, log into Reddit in that window, then `rap login`.

> Heads-up: a brand-new, history-less browser profile can hit Reddit's
> "blocked by network security" page. A real logged-in account (with a little
> normal browsing) clears it; a pristine automated profile may not.

## Quick start

```bash
rap doctor --with-browser          # check env, Chrome, JS-from-Apple-Events, login
rap config add-sub LocalLLaMA      # set a target subreddit
rap plan                           # where/what/when to post (planning engine)
rap draft LocalLLaMA --title "..." # score a draft before you post it
rap warmup start                   # begin the 7-day account warm-up
rap warmup plan                    # today's value-first comments (no links)
rap post LocalLLaMA --title "..." --type text --text "..."   # dry-run
rap post LocalLLaMA --title "..." --type text --text "..." --live   # actually post
rap schedule text --sub LocalLLaMA --title "..." --in-minutes 90
rap run --live                     # post everything that's due
```

Nothing writes to Reddit until you pass `--live`.

## Commands

| Command | What it does |
|---|---|
| `doctor [--with-browser]` | Environment + Chrome + session diagnostics |
| `browser launch\|status` | Manage the isolated CDP Chrome instance |
| `login` / `health` | Session status / best-effort shadowban probe |
| `plan [subs...]` | Full growth plan (best target, cross-posts, recipe, timing) |
| `compare [subs...]` | Rank subreddits by growth / viral / removal-safety |
| `draft <sub> --title ...` | Score a draft: acceptance risk + performance + fixes |
| `warmup start\|plan\|status\|ready` | 7-day account warm-up protocol |
| `post <sub> --title ... --live` | Submit a post now via the browser session |
| `comment <t3_id> --text ... --live` | Comment now |
| `schedule text\|link\|comment ...` | Queue an action for later |
| `queue list\|stats\|clear` | Inspect the queue |
| `run [--live]` | Process everything due |
| `config show\|init\|add-sub\|rm-sub` | Local config |

## How the pieces fit

- **Planning** — calls the [`reddit-growth-mcp`](https://github.com/latent-9/reddit-growth-mcp)
  CLI (`plan`, `compare`, `draft`). Credential-free: it reads the public Arctic
  archive, so it works before you even have an account.
- **Warm-up** — the 7-day "value-first, no links" protocol (patterned on
  [`oh-ashen-one/reddit-growth-skill`](https://github.com/oh-ashen-one/reddit-growth-skill)).
  Skip this and a new account gets shadowbanned the moment it promotes.
- **Acting** — AppleScript → Chrome → Reddit `/api/*` (technique from
  [`PHY041/claude-skill-reddit`](https://github.com/PHY041/claude-skill-reddit)).
- **Scheduling** — a SQLite queue (`~/.reddit-autopilot/queue.db`) plus
  `scripts/run_forever.sh` for a cron-like loop. Actions are spaced with human
  jitter.

See [CREDITS.md](CREDITS.md) for full attribution.

## Safety model

- Dry-run by default; every write needs `--live`.
- Human-paced spacing between actions, with jitter (`content.human_jitter`).
- No bulk account creation, no upvote/brigading, no proxy farms shipped.

## Responsible use

This tool automates **your own** Reddit account through your **own** logged-in
browser. Automating Reddit can violate Reddit's User Agreement; rate limits,
removals, and bans are real risks. Use it for legitimate community participation
and disclosed promotion only. You are responsible for what you post. There is no
warranty — see [LICENSE](LICENSE).

## Development

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest -q
```

## License

MIT.
