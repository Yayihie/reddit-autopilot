"""reddit-autopilot command line interface.

One entrypoint ties together the four subsystems:
  plan/draft/compare  -> planning backend (reddit-growth-mcp)
  warmup              -> account warm-up protocol
  post/comment        -> immediate actions via the browser session
  schedule/run/queue  -> the queue + scheduler
  doctor/login/health -> environment + session checks

Nothing that writes to Reddit runs unless --live is passed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

from reddit_autopilot import browser, browser_cdp, health, planner, queue, reddit_api, scheduler, warmup
from reddit_autopilot.config import Config


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def _require_live(args) -> bool:
    if not getattr(args, "live", False):
        print("(dry-run — nothing was posted. Re-run with --live to actually execute.)")
        return False
    return True


# --------------------------------------------------------------------------- commands

def cmd_doctor(args) -> int:
    _print(health.doctor(with_browser=args.with_browser))
    return 0


def cmd_login(args) -> int:
    _print(health.login_status())
    return 0


def cmd_health(args) -> int:
    _print(health.shadowban_probe(args.sub))
    return 0


def cmd_plan(args) -> int:
    subs = args.subs or Config.load().subreddits
    if not subs:
        print("No subreddits given. Pass them or run: rap config add-sub <name>")
        return 2
    if not planner.available():
        print("Planning backend not installed. Install with: pip install 'reddit-autopilot[growth]'")
        return 3
    res = planner.plan(subs, tz=args.tz)
    sys.stdout.write(res.get("stdout") or res.get("stderr") or "")
    return 0 if res.get("ok") else 1


def cmd_compare(args) -> int:
    subs = args.subs or Config.load().subreddits
    if not planner.available():
        print("Planning backend not installed. Install with: pip install 'reddit-autopilot[growth]'")
        return 3
    res = planner.compare(subs)
    sys.stdout.write(res.get("stdout") or res.get("stderr") or "")
    return 0 if res.get("ok") else 1


def cmd_draft(args) -> int:
    if not planner.available():
        print("Planning backend not installed. Install with: pip install 'reddit-autopilot[growth]'")
        return 3
    res = planner.draft(args.sub, args.title, args.type, args.body)
    sys.stdout.write(res.get("stdout") or res.get("stderr") or "")
    return 0 if res.get("ok") else 1


def cmd_warmup(args) -> int:
    c = Config.load()
    if args.action == "start":
        _print(warmup.start(c.get("warmup_days", 7), c.subreddits))
    elif args.action == "status":
        _print(warmup.status())
    elif args.action == "plan":
        _print(warmup.plan_day(c.get("warmup_comments_per_day", 3), c.subreddits or ["test"], args.topics))
    elif args.action == "ready":
        _print(warmup.check_ready())
    return 0


def cmd_post(args) -> int:
    if not _require_live(args):
        _print({"would_post": {"sub": args.sub, "title": args.title, "type": args.type, "url": args.url}})
        return 0
    who = reddit_api.whoami()
    if not who.get("logged_in"):
        print("Not logged in to Reddit in Chrome.")
        return 1
    if args.type == "link":
        res = reddit_api.submit_link(args.sub, args.title, args.url, who["modhash"])
    else:
        res = reddit_api.submit_text(args.sub, args.title, args.text or "", who["modhash"])
    _print(res)
    return 0 if res.get("ok") else 1


def cmd_comment(args) -> int:
    if not _require_live(args):
        _print({"would_comment": {"thing_id": args.thing_id, "text": args.text}})
        return 0
    who = reddit_api.whoami()
    if not who.get("logged_in"):
        print("Not logged in to Reddit in Chrome.")
        return 1
    res = reddit_api.comment(args.thing_id, args.text, who["modhash"])
    _print(res)
    return 0 if res.get("ok") else 1


def cmd_open_tab(args) -> int:
    tab = browser.open_tab(args.url or "https://www.reddit.com")
    _print({"opened": tab})
    return 0


def cmd_browser(args) -> int:
    if args.action == "launch":
        ok = browser_cdp.launch()
        _print({"launched": ok, "running": browser_cdp.running(), "profile": browser_cdp.profile_dir()})
        return 0 if ok else 1
    if args.action == "status":
        _print({
            "cdp_running": browser_cdp.running(),
            "version": (browser_cdp.version() or {}).get("Browser"),
            "reddit_tab": bool(browser_cdp.find_tab()),
            "profile": browser_cdp.profile_dir(),
            "guidance": "Run `rap browser launch`, log into Reddit in that window, then `rap login`.",
        })
        return 0
    return 2


def cmd_schedule(args) -> int:
    when = args.at
    if not when:
        minutes = args.in_minutes or 0
        when = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()
    if args.kind == "comment":
        item_id = queue.add("comment", args.thing_id, when, body=args.text)
    elif args.kind == "link":
        item_id = queue.add("submit_link", args.sub, when, title=args.title, url=args.url)
    else:
        item_id = queue.add("submit_text", args.sub, when, title=args.title, body=args.text)
    _print({"queued_id": item_id, "run_at": when, "kind": args.kind})
    return 0


def cmd_queue(args) -> int:
    if args.action == "list":
        _print(queue.all_items(args.status))
    elif args.action == "stats":
        _print(queue.stats())
    elif args.action == "clear":
        _print({"cleared": queue.clear(args.status or "done")})
    return 0


def cmd_run(args) -> int:
    if not args.live:
        print("(dry-run — the queue was inspected but nothing was posted. Add --live to execute.)")
    results = scheduler.run_due(live=args.live, spacing_seconds=0 if args.no_spacing else 45)
    _print({"processed": len(results), "results": results})
    return 0


def cmd_config(args) -> int:
    c = Config.load()
    if args.action == "show":
        _print(c.data)
    elif args.action == "init":
        c.save()
        _print({"wrote": str(c.path)})
    elif args.action == "add-sub":
        subs = set(c.subreddits)
        subs.add(args.name)
        c.set("target_subreddits", sorted(subs))
        c.save()
        _print({"subreddits": c.subreddits})
    elif args.action == "rm-sub":
        subs = [s for s in c.subreddits if s != args.name]
        c.set("target_subreddits", subs)
        c.save()
        _print({"subreddits": c.subreddits})
    return 0


# --------------------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="reddit-autopilot",
        description="All-in-one Reddit growth system: plan, warm up, schedule, and act "
                    "through your real browser session. No API keys.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="check the environment")
    d.add_argument("--with-browser", action="store_true", help="also probe a live Chrome tab")
    d.set_defaults(func=cmd_doctor)

    lg = sub.add_parser("login", help="show Reddit login/session status")
    lg.set_defaults(func=cmd_login)

    h = sub.add_parser("health", help="best-effort session/shadowban probe")
    h.add_argument("--sub", default="test")
    h.set_defaults(func=cmd_health)

    pl = sub.add_parser("plan", help="growth plan for target subreddits")
    pl.add_argument("subs", nargs="*", help="subreddits (defaults to config)")
    pl.add_argument("--tz", type=int, default=None)
    pl.set_defaults(func=cmd_plan)

    cp = sub.add_parser("compare", help="rank subreddits by growth/safety")
    cp.add_argument("subs", nargs="*")
    cp.set_defaults(func=cmd_compare)

    dr = sub.add_parser("draft", help="score a draft before posting")
    dr.add_argument("sub")
    dr.add_argument("--title", required=True)
    dr.add_argument("--type", default="text", choices=["text", "link", "image", "video"])
    dr.add_argument("--body", default=None)
    dr.set_defaults(func=cmd_draft)

    w = sub.add_parser("warmup", help="account warm-up protocol")
    w.add_argument("action", choices=["start", "status", "plan", "ready"])
    w.add_argument("--topics", nargs="*", default=None)
    w.set_defaults(func=cmd_warmup)

    po = sub.add_parser("post", help="submit a post now (needs --live)")
    po.add_argument("sub")
    po.add_argument("--title", required=True)
    po.add_argument("--type", default="text", choices=["text", "link"])
    po.add_argument("--text", default=None)
    po.add_argument("--url", default=None)
    po.add_argument("--live", action="store_true")
    po.set_defaults(func=cmd_post)

    co = sub.add_parser("comment", help="comment on a thing now (needs --live)")
    co.add_argument("thing_id", help="fullname, e.g. t3_abc123")
    co.add_argument("--text", required=True)
    co.add_argument("--live", action="store_true")
    co.set_defaults(func=cmd_comment)

    ot = sub.add_parser("open-tab", help="open a URL in Chrome and report the tab")
    ot.add_argument("url", nargs="?", default="https://www.reddit.com")
    ot.set_defaults(func=cmd_open_tab)

    br = sub.add_parser("browser", help="manage the isolated CDP Chrome instance")
    br.add_argument("action", choices=["launch", "status"])
    br.set_defaults(func=cmd_browser)

    sc = sub.add_parser("schedule", help="queue an action for later")
    sc.add_argument("kind", choices=["text", "link", "comment"])
    sc.add_argument("--sub", default=None)
    sc.add_argument("--thing-id", default=None)
    sc.add_argument("--title", default=None)
    sc.add_argument("--text", default=None)
    sc.add_argument("--url", default=None)
    sc.add_argument("--at", default=None, help="ISO8601 UTC time")
    sc.add_argument("--in-minutes", type=int, default=0)
    sc.set_defaults(func=cmd_schedule)

    q = sub.add_parser("queue", help="inspect the queue")
    q.add_argument("action", choices=["list", "stats", "clear"])
    q.add_argument("--status", default=None)
    q.set_defaults(func=cmd_queue)

    r = sub.add_parser("run", help="process due queue items (needs --live to post)")
    r.add_argument("--live", action="store_true")
    r.add_argument("--no-spacing", action="store_true")
    r.set_defaults(func=cmd_run)

    cf = sub.add_parser("config", help="manage local config")
    cf.add_argument("action", choices=["show", "init", "add-sub", "rm-sub"])
    cf.add_argument("name", nargs="?", default=None)
    cf.set_defaults(func=cmd_config)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except browser.BrowserError as e:
        print(f"browser error: {e}", file=sys.stderr)
        print("Run `rap doctor --with-browser` to diagnose.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
