#!/usr/bin/env python3
"""
token_economy_weekly.py — L3 runner: aggregate the last N days of waste,
append a row to baseline.csv, and write a _pending-review.md flag.

Runs fully deterministic (no LLM = 0 tokens) — ideal as a weekly cron/launchd
job. The "judgment + fix" step (turning flags into behavior changes) happens
while you're already in a session, so it costs no extra tokens.

Output directory is configurable:
    TE_DIR env var, default ~/.claude/token-economy

Usage: python3 token_economy_weekly.py [--days 7] [--stamp YYYY-MM-DD]
  (--stamp lets you pass the date explicitly if the runtime blocks date calls)
"""
import os, sys, json, subprocess, argparse, datetime

TE_DIR = os.environ.get("TE_DIR", os.path.expanduser("~/.claude/token-economy"))
BASELINE = os.path.join(TE_DIR, "baseline.csv")
PENDING = os.path.join(TE_DIR, "_pending-review.md")
SCAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token_waste_scan.py")


def run_scan(days):
    out = subprocess.run(
        [sys.executable, SCAN, "--since", str(days), "--json"],
        capture_output=True, text=True, timeout=300,
    ).stdout
    return json.loads(out)["reports"]


def aggregate(reports):
    return {
        "sessions": len(reports),
        "failed": sum(r["n_failed"] for r in reports),
        "waste_tokens": sum(r["est_waste_tokens_from_fails"] for r in reports),
        "redundant": sum(len(r["redundant_reads"]) for r in reports),
        "big_results": sum(len(r["big_results"]) for r in reports),
        "agent_spawns": sum(r["agent_spawns"] for r in reports),
        "workflow_spawns": sum(r["workflow_spawns"] for r in reports),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--stamp", default=None)
    args = ap.parse_args()
    stamp = args.stamp or datetime.date.today().isoformat()

    os.makedirs(TE_DIR, exist_ok=True)
    reports = run_scan(args.days)
    agg = aggregate(reports)

    header = "date,days,sessions,failed,waste_tokens,redundant,big_results,agent_spawns,workflow_spawns\n"
    if not os.path.exists(BASELINE):
        with open(BASELINE, "w") as f:
            f.write(header)
    with open(BASELINE, "a") as f:
        f.write(f"{stamp},{args.days},{agg['sessions']},{agg['failed']},{agg['waste_tokens']},"
                f"{agg['redundant']},{agg['big_results']},{agg['agent_spawns']},{agg['workflow_spawns']}\n")

    worst = sorted(reports, key=lambda r: -(r["n_failed"] * 3 + len(r["redundant_reads"]) + len(r["big_results"])))
    flagged = [r for r in worst if r["n_failed"] or r["redundant_reads"] or r["big_results"]][:8]
    lines = [f"# Token Economy — pending review ({stamp}, {args.days} days)\n",
             "> Data collected by the runner. Read this during a session, then turn it into actions in feedback-loop.md\n",
             f"- sessions: {agg['sessions']} · failed: {agg['failed']} (~{agg['waste_tokens']:,} tok) · "
             f"redundant reads: {agg['redundant']} · big dumps: {agg['big_results']} · "
             f"agents: {agg['agent_spawns']} · workflows: {agg['workflow_spawns']}\n", "\n## Worst offenders\n"]
    for r in flagged:
        bits = []
        if r["n_failed"]:
            tools = ", ".join(sorted({f["tool"] for f in r["failed"]}))
            bits.append(f"{r['n_failed']} fail ({tools})")
        if r["redundant_reads"]:
            bits.append(f"{len(r['redundant_reads'])} re-read")
        if r["big_results"]:
            bits.append(f"{len(r['big_results'])} big dump")
        if r["workflow_spawns"]:
            bits.append(f"{r['workflow_spawns']} workflow")
        lines.append(f"- `{r['session'][:8]}`: {' / '.join(bits)}\n")
    with open(PENDING, "w") as f:
        f.writelines(lines)

    print(f"baseline += 1 row ({stamp}) · flag -> {PENDING}")
    print(json.dumps(agg, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
