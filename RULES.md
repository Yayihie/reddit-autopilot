# Reddit rules this tool enforces

Reddit does not publish one "automation policy". Enforcement happens at three
layers, and this tool has a guard for each. Source of truth: Reddit's Content
Policy (Rule 2) and the sitewide self-promotion guidance, plus per-subreddit
rules and AutoMod.

## The rules (why accounts get banned or flagged as spam)

1. **Content Policy Rule 2 - authentic participation, no spam or manipulation.**
   Banned: repeatedly posting the same link, vote manipulation, running networks
   of accounts that promote the same thing, and evading a ban with a new account.

2. **Self-promotion guidance (the "9:1 rule").** Not a number Reddit tracks, but
   an account that mostly links its own stuff reads as a spam account regardless
   of the exact ratio. Contribute genuinely far more often than you promote.

3. **Rate limits / cooldowns.** New and low-karma accounts are throttled hard
   ("Looks like you've been doing that a lot. Take a break for 5 minutes").
   Repeated 429s escalate toward bans.

4. **Karma and account-age gates.** Many subs set minimum karma and/or account
   age; AutoMod silently removes posts below them.

5. **CQS (Contributor Quality Score).** Reddit's internal quality score. Low CQS
   lands your content in the spam filter - visible to you, invisible to others.

6. **Shadowbans.** Sitewide or sub-level. Your content looks fine to you but is
   removed for everyone else.

7. **Per-subreddit rules.** Each sub has its own rules and AutoMod: link-domain
   bans, flair requirements, daily threads, "no promotion" rules.

8. **Disclosure.** Promoting something you benefit from without disclosing your
   connection violates Rule 2 (and, in the US, FTC guidance).

## How `reddit-autopilot` enforces them

Guard lives in `policy.py`; state in `~/.reddit-autopilot/policy-state.json`.

| Rule | Guard |
|---|---|
| 1 - no spam/repeated links | `max_subs_per_link_per_day` = 1: the same URL can never be posted to more than one sub per day. |
| 1 - no manipulation | The tool never votes or manipulates; only posts/comments as the logged-in account. |
| 2 - self-promo ratio | `nonlink_per_link` = 9: a linked comment is flagged (soft) when non-link activity is below 9x links. |
| 3 - rate limits | `min_minutes_between_actions` (20), `max_actions_per_hour` (6), and automatic cooldown capture: any `RATELIMIT` response sets a 300s+ block. |
| 4 - karma/age gates | `min_comment_karma`, `min_account_age_days` (exposed via `whoami`); warm up first. |
| 5/6 - CQS / shadowban | Post-publish verification (fetch the thread back and confirm the comment appears); a missing comment is a shadow-removal signal. |
| 7 - per-sub rules | `rap login`/`subreddit_rules` can pull a sub's rules; keep an allowlist of target subs. |
| 8 - disclosure | Content guardrails in the PWG skills; never claim a false identity. |
| crisis content | `CRISIS_KEYWORDS` block: never attach a link in a suicide/self-harm/abuse thread. |

## Daily cadence the tool assumes

- **1 linked comment per day, across all subs** (`max_linked_comments_per_day`).
- Everything else that day is genuine, non-promotional participation.
- Human pacing with jitter; hard cap of 6 actions/hour.

## Commands

```
rap policy          # limits + today's counts and any active cooldown
```

Hard violations block the action (CLI returns nonzero, scheduler marks the item
`skipped`); soft violations print a warning and proceed.
