# Credits & prior art

reddit-autopilot is an orchestration layer that stands on the shoulders of several
strong open-source projects. Individual algorithms and ideas are re-implemented
here; where a project is used as a live backend it is called out explicitly.

## Used as live backends
| Project | License | What we use |
|---|---|---|
| [latent-9/reddit-growth-mcp](https://github.com/latent-9/reddit-growth-mcp) | MIT | The `plan/compare/draft/patterns` planning engine. Called as the `reddit-growth` CLI (install with the `[growth]` extra). |
| [1146345502/reddit-skills](https://github.com/1146345502/reddit-skills) | MIT | The optional websocket "extension bridge" action backend (`[bridge]` extra). |

## Ideas / patterns re-implemented
| Project | License | Idea borrowed |
|---|---|---|
| [PHY041/claude-skill-reddit](https://github.com/PHY041/claude-skill-reddit) | (see repo) | The AppleScript → Chrome → Reddit `/api/*` technique for undetectable posting (our `browser` + `reddit_api` modules). |
| [oh-ashen-one/reddit-growth-skill](https://github.com/oh-ashen-one/reddit-growth-skill) | (see repo) | The 7-day "no links, value-first comments" account warm-up protocol (our `warmup` module). |
| [MrPowerScripts/reddit-karma-farming-bot](https://github.com/MrPowerScripts/reddit-karma-farming-bot) | MIT | Config-driven warm-up/karma approach. |
| [ibid-11962/reddit-post-scheduler](https://github.com/ibid-11962/reddit-post-scheduler) | (see repo) | The queue/schedule-the-post shape. |

If you are one of these authors and want attribution changed or removed, open an issue.

## Not included on purpose
The tool deliberately does **not** ship bulk account creation, upvote/brigading
bots, or proxy/fingerprint-rotation farms. Those approaches are the fastest route
to a permanent Reddit ban and generally violate Reddit's User Agreement. See the
"Responsible use" section of the README.
