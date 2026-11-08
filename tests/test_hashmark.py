"""Offline Hashmark profile tests. No Reddit, Chrome, CDP, or credentials."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


def _boom(*_a, **_k):
    raise AssertionError("network/session must not run in this test")


class HashmarkIsolationTest(unittest.TestCase):
    def setUp(self):
        self._old = {k: os.environ.get(k) for k in ("RAP_PROFILE", "REDDIT_AUTOPILOT_HOME")}
        os.environ.pop("RAP_PROFILE", None)
        os.environ.pop("REDDIT_AUTOPILOT_HOME", None)

    def tearDown(self):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_profile_home_is_isolated_from_default(self):
        from reddit_autopilot import config

        default = config.home()
        os.environ["RAP_PROFILE"] = "hashmark"
        hashmark = config.home()
        os.environ["RAP_PROFILE"] = "pwg"
        pwg = config.home()
        self.assertEqual(default, Path.home() / ".reddit-autopilot")
        self.assertEqual(hashmark, Path.home() / ".reddit-autopilot" / "profiles" / "hashmark")
        self.assertEqual(pwg, Path.home() / ".reddit-autopilot" / "profiles" / "pwg")
        self.assertNotEqual(hashmark, default)
        self.assertNotEqual(hashmark, pwg)

    def test_home_env_overrides_profile(self):
        from reddit_autopilot import config

        tmp = tempfile.mkdtemp()
        os.environ["RAP_PROFILE"] = "hashmark"
        os.environ["REDDIT_AUTOPILOT_HOME"] = tmp
        self.assertEqual(config.home(), Path(tmp))

    def test_invalid_profile_rejected(self):
        from reddit_autopilot import config

        os.environ["RAP_PROFILE"] = "../etc"
        with self.assertRaises(ValueError):
            config.profile_name()


class HashmarkActivationTest(unittest.TestCase):
    def setUp(self):
        os.environ["REDDIT_AUTOPILOT_HOME"] = tempfile.mkdtemp()
        os.environ["RAP_PROFILE"] = "hashmark"

    def tearDown(self):
        os.environ.pop("RAP_PROFILE", None)
        os.environ.pop("REDDIT_AUTOPILOT_HOME", None)

    def test_packaged_template_loads(self):
        from reddit_autopilot.config import Config

        c = Config.load()
        self.assertEqual(c.brand, "hashmark")
        self.assertFalse(c.get("live_sends_enabled"))
        self.assertTrue(c.get("activation_blocked"))
        self.assertEqual(c.get("disclosure"), "I'm on the Hashmark team")
        self.assertEqual(c.subreddits, [])

    def test_live_blockers_include_oauth_gap_and_date(self):
        from reddit_autopilot import activation

        blocked = activation.blockers(live=True, kind="comment")
        joined = " ".join(blocked)
        self.assertTrue(blocked)
        self.assertIn("live_sends_enabled", joined)
        self.assertIn("parent-managed saved routine", joined)
        self.assertIn("OAuth", joined)
        self.assertIn("2026-11-09", joined)
        self.assertEqual(activation.blockers(live=False), [])

    def test_get_session_blocked_without_calling_cdp(self):
        from reddit_autopilot import activation, reddit_api

        with patch("reddit_autopilot.browser_cdp.running", side_effect=_boom), \
             patch("reddit_autopilot.browser.ensure_reddit_session", side_effect=_boom):
            with self.assertRaises(activation.SessionBlocked):
                reddit_api.get_session()

    def test_cdp_launch_blocked(self):
        from reddit_autopilot import activation, browser_cdp

        with patch("subprocess.run", side_effect=_boom):
            with self.assertRaises(activation.SessionBlocked):
                browser_cdp.launch()


class HashmarkCliTest(unittest.TestCase):
    def setUp(self):
        os.environ["REDDIT_AUTOPILOT_HOME"] = tempfile.mkdtemp()
        os.environ.pop("RAP_PROFILE", None)

    def tearDown(self):
        os.environ.pop("RAP_PROFILE", None)
        os.environ.pop("REDDIT_AUTOPILOT_HOME", None)

    def test_dry_run_post_does_not_call_session(self):
        from reddit_autopilot import cli, reddit_api

        with patch.object(reddit_api, "whoami", side_effect=_boom), \
             patch.object(reddit_api, "get_session", side_effect=_boom), \
             patch.object(reddit_api, "submit_text", side_effect=_boom):
            rc = cli.main(["post", "test", "--title", "hi", "--text", "hello there"])
        self.assertEqual(rc, 0)

    def test_hashmark_live_post_blocked_without_session(self):
        from reddit_autopilot import cli, reddit_api

        with patch.object(reddit_api, "whoami", side_effect=_boom), \
             patch.object(reddit_api, "get_session", side_effect=_boom), \
             patch.object(reddit_api, "submit_text", side_effect=_boom):
            rc = cli.main(["--profile", "hashmark", "post", "test", "--title", "hi", "--text", "hello there", "--live"])
        self.assertEqual(rc, 1)

    def test_hashmark_login_blocked_without_session(self):
        from reddit_autopilot import cli, reddit_api

        with patch.object(reddit_api, "whoami", side_effect=_boom):
            rc = cli.main(["--profile", "hashmark", "login"])
        self.assertEqual(rc, 1)

    def test_hashmark_plan_blocked(self):
        from reddit_autopilot import cli, planner

        with patch.object(planner, "plan", side_effect=_boom), \
             patch.object(planner, "available", return_value=True):
            rc = cli.main(["--profile", "hashmark", "plan", "fantasyfootball"])
        self.assertEqual(rc, 1)

    def test_hashmark_run_live_blocked(self):
        from reddit_autopilot import cli, reddit_api, scheduler

        with patch.object(reddit_api, "whoami", side_effect=_boom), \
             patch.object(scheduler, "_execute", side_effect=_boom):
            rc = cli.main(["--profile", "hashmark", "run", "--live"])
        self.assertEqual(rc, 1)

    def test_hashmark_text_post_with_url_is_a_linked_action(self):
        from reddit_autopilot import policy

        os.environ["RAP_PROFILE"] = "hashmark"
        res = policy.check(
            "submit_text",
            "fantasyfootball",
            link=False,
            texts=[
                "I'm on the Hashmark team. Free, no buy-in, credits only. "
                "https://playhashmark.com/football"
            ],
        )
        self.assertFalse(res["ok"])
        self.assertTrue(any("warm-up mode" in h or "link" in h.lower() for h in res["hard"]))

    def test_hashmark_promotional_without_disclosure_fails_dry_run(self):
        from reddit_autopilot import cli, reddit_api

        text = "Check https://playhashmark.com/football for The Cut Line weekly lowest-score elimination."
        with patch.object(reddit_api, "whoami", side_effect=_boom):
            rc = cli.main(["--profile", "hashmark", "comment", "t3_x", "--text", text])
        self.assertEqual(rc, 1)

    def test_hashmark_positive_buyin_still_blocked(self):
        from reddit_autopilot import brand

        os.environ["RAP_PROFILE"] = "hashmark"
        res = brand.check(
            "comment", "fantasyfootball",
            texts=["I'm on the Hashmark team. $50 buy-in this week at https://playhashmark.com"],
            link=True,
            url="https://playhashmark.com/football",
        )
        self.assertFalse(res["ok"])
        self.assertTrue(any("buy-in" in h for h in res["hard"]))

    def test_hashmark_guillotine_claim_blocked(self):
        from reddit_autopilot import brand

        os.environ["RAP_PROFILE"] = "hashmark"
        res = brand.check(
            "comment", "fantasyfootball",
            texts=["Our guillotine league is live at https://playhashmark.com I'm on the Hashmark team"],
            link=True,
            url="https://playhashmark.com/football",
        )
        self.assertFalse(res["ok"])
        self.assertTrue(any("guillotine" in h for h in res["hard"]))

    def test_hashmark_waiver_claim_blocked(self):
        from reddit_autopilot import brand

        os.environ["RAP_PROFILE"] = "hashmark"
        res = brand.check(
            "comment", "fantasybball",
            texts=["I'm on the Hashmark team. An eliminated roster hits the waiver wire."],
            link=True,
            url="https://playhashmark.com/basketball",
        )
        self.assertFalse(res["ok"])

    def test_hashmark_disclosed_promo_ok_for_brand_layer(self):
        from reddit_autopilot import brand

        os.environ["RAP_PROFILE"] = "hashmark"
        res = brand.check(
            "comment", "fantasyfootball",
            texts=[
                "I'm on the Hashmark team. The Cut Line is weekly lowest-score elimination. "
                "Free, no buy-in, credits only."
            ],
            link=True,
            url="https://playhashmark.com/football",
        )
        self.assertTrue(res["ok"], res)

    def test_hashmark_forbids_votes(self):
        from reddit_autopilot import reddit_api, warmup

        os.environ["RAP_PROFILE"] = "hashmark"
        with patch.object(reddit_api, "whoami", side_effect=_boom), \
             patch.object(warmup, "fetch_recent", side_effect=_boom):
            res = warmup.upvote_recent(["fantasyfootball"], live=False)
        self.assertFalse(res["ok"])
        self.assertIn("vote", res["blocked"].lower())

    def test_hashmark_warmup_bank_has_no_fake_experience(self):
        from reddit_autopilot import content

        os.environ["RAP_PROFILE"] = "hashmark"
        comments = content.warmup_comments(3)
        blob = " ".join(comments).lower()
        self.assertNotIn("matches my experience", blob)
        self.assertNotIn("helped me", blob)

    def test_hashmark_scheduler_dry_run_still_local(self):
        from reddit_autopilot import queue, reddit_api, scheduler

        os.environ["RAP_PROFILE"] = "hashmark"
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        queue.add("comment", "t3_x", past, body="hello from a dry run comment that is long enough")
        with patch.object(reddit_api, "whoami", side_effect=_boom), \
             patch.object(reddit_api, "comment", side_effect=_boom):
            results = scheduler.run_due(live=False, spacing_seconds=0)
        self.assertEqual(results[0]["status"], "dry-run")

    def test_default_profile_is_not_hashmark_gated(self):
        from reddit_autopilot import activation

        os.environ.pop("RAP_PROFILE", None)
        self.assertFalse(activation.is_hashmark())
        self.assertEqual(activation.blockers(live=True, kind="comment"), [])

    def test_parser_accepts_profile_flag(self):
        from reddit_autopilot.cli import build_parser

        args = build_parser().parse_args(["--profile", "hashmark", "profile"])
        self.assertEqual(args.profile, "hashmark")

    def test_run_forever_defaults_to_dry_and_refuses_hashmark_live(self):
        text = Path("scripts/run_forever.sh").read_text()
        self.assertIn('LIVE_FLAG=""', text)
        self.assertIn('RAP_PROFILE:-}" == "hashmark"', text)
        self.assertIn('Hashmark live loop is disabled', text)
        self.assertIn('if [[ "${LIVE:-0}" == "1"', text)


if __name__ == "__main__":
    unittest.main()
