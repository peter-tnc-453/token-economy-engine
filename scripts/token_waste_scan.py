#!/usr/bin/env python3
"""
token_waste_scan.py — L2: find "tokens burned for nothing" in Claude Code usage.

Parses the transcript JSONL that Claude Code writes under
~/.claude/projects/<project>/<session>.jsonl and flags 5 kinds of waste that
are auto-detectable from the transcript, then estimates the wasted tokens — so
you can feed L3 (the feedback loop), change behavior, and re-measure.

Usage:
    python3 token_waste_scan.py                  # all sessions touched in the last 7 days
    python3 token_waste_scan.py --since 1        # last 1 day
    python3 token_waste_scan.py --session <uuid> # a single session
    python3 token_waste_scan.py --json           # JSON output (for aggregation)

Note: tokens are estimated as chars/4 (heuristic) — a proportional signal to
locate fixes, not a real bill.
"""
import sys, os, json, glob, time, argparse
from collections import defaultdict

PROJECTS = os.path.expanduser("~/.claude/projects")
CHARS_PER_TOKEN = 4

# tuning: a tool_result larger than this bloats context
BIG_RESULT_CHARS = 20_000          # ~5k tokens
# a Bash result that dumps a lot (full env, full table, ...)
BIG_BASH_CHARS = 8_000             # ~2k tokens


def est_tokens(chars):
    return chars // CHARS_PER_TOKEN


def iter_blocks(obj):
    msg = obj.get("message", {})
    content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict):
                yield b


def scan_session(path):
    """Return a waste summary for one session."""
    sid = os.path.splitext(os.path.basename(path))[0]
    tool_use_by_id = {}          # tool_use_id -> (name, input)
    read_files = defaultdict(int)
    failed = []                  # [{tool, chars}]
    big_results = []             # [{tool, chars}]
    big_bash = []                # [{cmd, chars}]
    agent_spawns = 0
    workflow_spawns = 0
    n_tool_calls = 0

    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except Exception:
                continue
            for b in iter_blocks(o):
                bt = b.get("type")
                if bt == "tool_use":
                    n_tool_calls += 1
                    nm = b.get("name", "?")
                    inp = b.get("input", {}) or {}
                    tool_use_by_id[b.get("id")] = (nm, inp)
                    if nm == "Read":
                        fp = inp.get("file_path", "")
                        if fp:
                            read_files[fp] += 1
                    elif nm in ("Agent", "Task"):
                        agent_spawns += 1
                    elif nm == "Workflow":
                        workflow_spawns += 1
                elif bt == "tool_result":
                    nm, inp = tool_use_by_id.get(b.get("tool_use_id"), ("?", {}))
                    raw = b.get("content", "")
                    chars = len(raw if isinstance(raw, str) else json.dumps(raw))
                    if b.get("is_error"):
                        failed.append({"tool": nm, "chars": chars})
                    if chars > BIG_RESULT_CHARS:
                        big_results.append({"tool": nm, "chars": chars})
                    if nm == "Bash" and chars > BIG_BASH_CHARS:
                        cmd = (inp.get("command", "") or "")[:80]
                        big_bash.append({"cmd": cmd, "chars": chars})

    redundant = {f: c for f, c in read_files.items() if c > 1}

    # estimate wasted tokens (proportional):
    #   - failed calls: the whole failed result
    #   - redundant reads: counted as a flag, not summed into tokens
    waste_tokens = est_tokens(sum(f["chars"] for f in failed))

    return {
        "session": sid,
        "mtime": os.path.getmtime(path),
        "n_tool_calls": n_tool_calls,
        "failed": failed,
        "n_failed": len(failed),
        "big_results": sorted(big_results, key=lambda x: -x["chars"])[:5],
        "big_bash": sorted(big_bash, key=lambda x: -x["chars"])[:5],
        "redundant_reads": redundant,
        "agent_spawns": agent_spawns,
        "workflow_spawns": workflow_spawns,
        "est_waste_tokens_from_fails": waste_tokens,
    }


def collect(since_days=None, session=None):
    files = glob.glob(os.path.join(PROJECTS, "*", "*.jsonl"))
    if session:
        files = [f for f in files if session in os.path.basename(f)]
    elif since_days is not None:
        cutoff = time.time() - since_days * 86400
        files = [f for f in files if os.path.getmtime(f) >= cutoff]
    return sorted(files, key=os.path.getmtime, reverse=True)


def human(reports):
    if not reports:
        print("No sessions in the selected window.")
        return
    tot_fail = sum(r["n_failed"] for r in reports)
    tot_waste = sum(r["est_waste_tokens_from_fails"] for r in reports)
    tot_redundant = sum(len(r["redundant_reads"]) for r in reports)
    tot_big = sum(len(r["big_results"]) for r in reports)
    tot_wf = sum(r["workflow_spawns"] for r in reports)
    tot_ag = sum(r["agent_spawns"] for r in reports)

    print("=" * 60)
    print(f"TOKEN WASTE SCAN — {len(reports)} sessions")
    print("=" * 60)
    print(f"  Failed tool calls:    {tot_fail}  (~{tot_waste:,} tokens burned)")
    print(f"  Redundant reads:      {tot_redundant} files re-read")
    print(f"  Big results (>5k tok):{tot_big} (context bloat)")
    print(f"  Agent spawns: {tot_ag}  |  Workflow: {tot_wf}  (check over-tooling)")
    print()
    worst = sorted(reports, key=lambda r: -(r["n_failed"] * 3 + len(r["redundant_reads"]) + len(r["big_results"])))
    flagged = [r for r in worst if r["n_failed"] or r["redundant_reads"] or r["big_results"]][:8]
    if flagged:
        print("  Worst offenders (most waste):")
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
            print(f"   - {r['session'][:8]}: {' / '.join(bits)}")
    else:
        print("  Clean — no auto-detectable waste in this window.")
    print()
    print("  next: review flags -> 1-2 concrete fixes -> feedback-loop.md -> re-measure")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=float, default=None, help="last N days (default 7)")
    ap.add_argument("--session", default=None, help="a single session uuid")
    ap.add_argument("--json", action="store_true", help="JSON output")
    args = ap.parse_args()

    since = args.since if (args.since is not None or args.session) else 7
    files = collect(since_days=(None if args.session else since), session=args.session)
    reports = [scan_session(f) for f in files]

    if args.json:
        print(json.dumps({"reports": reports}, ensure_ascii=False, indent=2))
    else:
        human(reports)
    return 0


if __name__ == "__main__":
    sys.exit(main())
