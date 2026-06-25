# Token Economy Engine

> Find the tokens you burn for nothing in **Claude Code** — then fix the root cause and re-measure, week after week.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)
![Dependencies](https://img.shields.io/badge/runtime%20deps-stdlib%20only-brightgreen.svg)
![Local](https://img.shields.io/badge/runs-100%25%20local-black.svg)

A cost report tells you the temperature. This tells you **where the fever is** — and closes a feedback loop to bring it down.

Everything runs **100% locally** by reading the transcript JSONL that Claude Code already writes to `~/.claude/projects/**/*.jsonl`. No account, no cloud, no paid service.

```
============================================================
TOKEN WASTE SCAN — 62 sessions
============================================================
  Failed tool calls:    162  (~18,883 tokens burned)
  Redundant reads:      94 files re-read
  Big results (>5k tok):108 (context bloat)
  Agent spawns: 326  |  Workflow: 16  (check over-tooling)

  Worst offenders (most waste):
   - 51163cc6: 9 fail (Bash, Edit, SendUserFile, TaskStop) / 3 workflow
   - e5fd48b2: 2 fail (Edit) / 4 re-read / 5 big dump / 2 workflow
   ...
  next: review flags -> 1-2 concrete fixes -> feedback-loop.md -> re-measure
```

## Why

LLM agents quietly waste tokens: failed tool calls, re-reading files already in
context, dumping whole files when a few lines would do, spinning up multi-agent
workflows where one direct answer fits. Individually small — at scale, real
money (or rate-limit headroom). Most "be efficient" rules already live in your
config; the value here is **turning that into data that proves whether you
actually follow them**, then compounding the fixes.

## How it works — 3 layers

| Layer | Does | Tool |
|---|---|---|
| **L1 — Measure** | token/cost breakdown for one session | `scripts/session_cost.py <session-uuid>` |
| **L2 — Detect** | parse transcripts, flag 5 kinds of waste | `scripts/token_waste_scan.py [--since N \| --session uuid] [--json]` |
| **L3 — Loop** | aggregate → `baseline.csv` → flag → action → re-measure | `scripts/token_economy_weekly.py` |

L1 uses [`ccusage`](https://github.com/ryoppippi/ccusage) (`npx ccusage@latest`) for pricing. L2/L3 are **pure stdlib** — zero dependencies.

> 💰 The `cost` figures are the *API-equivalent* list price, **not a real bill** if you're on a flat subscription. Treat them as a "how heavy / how wasteful" signal.

## The 5 waste types (auto-detected)

1. **Failed tool calls** — errors that burn tokens for nothing
2. **Redundant reads** — re-reading a file already in context
3. **Big dumps** — oversized tool results that bloat the context window
4. **Over-tooling** — more agent/workflow spawns than the task needs (flagged for a human call)
5. **Verbose shell** — full `env` / full-table dumps where `head`/`grep` would do

## The feedback loop (cheap by design)

1. **Collect data = deterministic, 0 tokens** — `token_economy_weekly.py` runs weekly (launchd/cron), appends `baseline.csv`, writes `_pending-review.md`.
2. **Judge + fix = while you're already in a session** — read the flag, turn it into 1–2 concrete behavior changes in `feedback-loop.md`. No extra tokens spent.
3. **Re-measure next week** — `baseline.csv` shows whether the numbers actually dropped.

See [`templates/feedback-loop.md`](templates/feedback-loop.md) for the starting structure.

## Install

```bash
git clone https://github.com/peter-tnc-453/token-economy-engine.git
cd token-economy-engine
./install.sh        # copies scripts to ~/.claude/scripts, creates the data dir,
                    # and (optionally) registers a weekly launchd job on macOS
```

Or just run it straight from the repo:

```bash
python3 scripts/token_waste_scan.py --since 7
python3 scripts/session_cost.py <session-uuid>
```

The weekly runner writes to `$TE_DIR` (default `~/.claude/token-economy`):

```bash
TE_DIR=~/my-notes/token-economy python3 scripts/token_economy_weekly.py --days 7
```

## Layout

```
scripts/      the three core tools
templates/    launchd plist, feedback-loop.md, baseline.csv (header only)
install.sh    one-shot installer
```

## Notes

- Built for **Claude Code**'s transcript format (`~/.claude/projects/<project>/<uuid>.jsonl`).
- Token estimates in L2 use a `chars / 4` heuristic — a proportional signal to locate fixes, not an exact count.
- No personal data ships in this repo; runtime data (`baseline.csv`, `_pending-review.md`, logs) is git-ignored.

## License

MIT — see [LICENSE](LICENSE).
