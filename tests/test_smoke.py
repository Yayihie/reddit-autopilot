"""Smoke tests: exercise the zero-dependency core without touching Reddit."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone


class TestCore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["REDDIT_AUTOPILOT_HOME"] = self.tmp
        os.environ.pop("RAP_PROFILE", None)
        # re-import so the module-level paths pick up the temp home
        import importlib

        from reddit_autopilot import config
        importlib.reload(config)

    def test_config_defaults(self):
        from reddit_autopilot import config

        c = config.Config.load()
        self.assertEqual(c.subreddits, [])
        c.set("target_subreddits", ["python"])
        c.save()
        c2 = config.Config.load()
        self.assertEqual(c2.subreddits, ["python"])

    def test_queue_add_due_mark(self):
        from reddit_autopilot import queue

        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        qid = queue.add("submit_text", "test", past, title="hi", body="body")
        due = queue.due()
        self.assertTrue(any(d["id"] == qid for d in due))
        queue.mark(qid, "done", "{}")
        self.assertNotIn(qid, [d["id"] for d in queue.due()])
        self.assertEqual(queue.stats().get("done"), 1)

    def test_content_jitter_is_randomized(self):
        from reddit_autopilot import content

        delays = {content.human_jitter(90).total_seconds() for _ in range(20)}
        self.assertGreater(len(delays), 1, "jitter should not be constant")

    def test_warmup_plan_shape(self):
        from reddit_autopilot import warmup

        plan = warmup.plan_day(per_day=3, subs=["python"])
        self.assertEqual(len(plan["items"]), 3)
        for item in plan["items"]:
            self.assertIn("text", item)
            self.assertEqual(item["sub"], "python")

    def test_parser_builds(self):
        from reddit_autopilot.cli import build_parser

        p = build_parser()
        args = p.parse_args(["schedule", "text", "--sub", "python", "--title", "t", "--in-minutes", "5"])
        self.assertEqual(args.kind, "text")
        self.assertEqual(args.sub, "python")

    def test_dry_run_comment_does_not_call_network(self):
        from unittest.mock import patch

        from reddit_autopilot import cli, reddit_api

        def boom(*_a, **_k):
            raise AssertionError("dry-run must not open a Reddit session")

        args = cli.build_parser().parse_args(["comment", "t3_x", "--text", "hello"])
        with patch.object(reddit_api, "whoami", side_effect=boom), \
             patch.object(reddit_api, "get_session", side_effect=boom), \
             patch.object(reddit_api, "comment", side_effect=boom):
            rc = cli.cmd_comment(args)  # no --live -> safe
        self.assertEqual(rc, 0)


class TestSchedulerDryRun(unittest.TestCase):
    def test_run_due_dry(self):
        import importlib
        import os
        import tempfile

        os.environ["REDDIT_AUTOPILOT_HOME"] = tempfile.mkdtemp()
        from reddit_autopilot import queue
        importlib.reload(queue)
        from reddit_autopilot import scheduler
        importlib.reload(scheduler)

        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        queue.add("comment", "t3_x", past, body="hi")
        results = scheduler.run_due(live=False, spacing_seconds=0)
        self.assertEqual(results[0]["status"], "dry-run")


if __name__ == "__main__":
    unittest.main()
