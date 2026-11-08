"""Tests for the Reddit policy guardrails."""

import importlib
import os
import tempfile
import time
import unittest


def fresh(mode="normal"):
    os.environ.pop("RAP_PROFILE", None)
    os.environ["REDDIT_AUTOPILOT_HOME"] = tempfile.mkdtemp()
    from reddit_autopilot import config, policy

    importlib.reload(config)
    importlib.reload(policy)
    c = config.Config.load()
    c.set("mode", mode)
    c.save()
    return policy


class TestPolicy(unittest.TestCase):
    def test_first_link_allowed_but_ratio_soft(self):
        p = fresh()
        res = p.check("comment", "Christian", link=True, url="https://x.org")
        self.assertTrue(res["ok"], res)
        self.assertTrue(res["soft"], "9:1 ratio should warn on a cold account")

    def test_second_link_same_day_blocked(self):
        p = fresh()
        p.record_action("comment", "Christian", link=True, url="https://a.org")
        res = p.check("comment", "Christian", link=True, url="https://b.org")
        self.assertFalse(res["ok"])
        self.assertTrue(any("cap is" in h for h in res["hard"]))

    def test_same_url_spray_blocked(self):
        p = fresh()
        p.record_action("submit_link", "Christian", link=True, url="https://a.org")
        res = p.check("submit_link", "Christian", link=True, url="https://a.org")
        self.assertFalse(res["ok"])

    def test_crisis_keyword_blocks(self):
        p = fresh()
        res = p.check("comment", "Christian", texts=["I want to die tonight"])
        self.assertFalse(res["ok"])
        self.assertTrue(any("crisis" in h for h in res["hard"]))

    def test_min_gap_blocks(self):
        p = fresh()
        p.record_action("comment", "Christian")
        res = p.check("comment", "Christian")
        self.assertFalse(res["ok"], "second action immediately should be blocked")

    def test_ratelimit_sets_cooldown(self):
        p = fresh()
        p.record_ratelimit(300)
        res = p.check("comment", "Christian")
        self.assertFalse(res["ok"])
        self.assertTrue(any("cooldown" in h for h in res["hard"]))
        st = p.status()
        self.assertTrue(st["ratelimit_active"])

    def test_hourly_cap(self):
        p = fresh()
        base = time.time() - 1000
        for i in range(6):
            p.record_action("comment", "Christian", ts=base + i)
        # last action is ~1000s ago so the min-gap passes; hourly cap should trip
        res = p.check("comment", "Christian")
        self.assertFalse(res["ok"])

    def test_url_in_text_counts_as_link(self):
        p = fresh(mode="warmup")
        res = p.check("submit_text", "Christian", texts=["read https://pacewithgrace.org"])
        self.assertFalse(res["ok"])
        self.assertTrue(any("warm-up mode" in h for h in res["hard"]))

    def test_has_link(self):
        p = fresh()
        self.assertTrue(p.has_link("see https://www.pacewithgrace.org/bible-verses/doubt"))
        self.assertFalse(p.has_link("no links here at all"))

    def test_link_blocked_below_comment_karma(self):
        p = fresh()
        res = p.check("comment", "Christian", link=True, url="https://x.org", comment_karma=2)
        self.assertFalse(res["ok"])
        self.assertTrue(any("comment karma" in h for h in res["hard"]))

    def test_link_allowed_with_enough_karma(self):
        p = fresh()
        res = p.check("comment", "Christian", link=True, url="https://x.org", comment_karma=200)
        self.assertTrue(res["ok"], res["hard"])

    def test_link_blocked_for_young_account(self):
        p = fresh()
        res = p.check("comment", "Christian", link=True, url="https://x.org", age_days=2)
        self.assertFalse(res["ok"])
        self.assertTrue(any("old" in h for h in res["hard"]))

    def test_warmup_mode_blocks_links(self):
        p = fresh(mode="warmup")
        res = p.check("comment", "Christian", link=True, url="https://x.org", comment_karma=500)
        self.assertFalse(res["ok"])
        self.assertTrue(any("warm-up mode" in h for h in res["hard"]))


if __name__ == "__main__":
    unittest.main()
