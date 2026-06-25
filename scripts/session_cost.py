#!/usr/bin/env python3
"""
session_cost.py — L1: token + cost breakdown for a single Claude Code session.

How it works: ccusage groups usage per session by a `period` field that equals
the session UUID, which is also the transcript filename
(~/.claude/projects/<project>/<uuid>.jsonl). This finds the matching session
and prints its token/cost breakdown.

Usage:
    python3 session_cost.py [SESSION_UUID]
      no arg        -> guess current session = most recently modified .jsonl
                       (pass the UUID explicitly if several sessions run at once)
      SESSION_UUID  -> use that session directly

Note: `cost` is the *equivalent* API list price, not a real bill — on a flat
subscription you don't pay per token. Treat it as a "how heavy / how wasteful"
signal, not an invoice.
"""
import sys, os, json, glob, subprocess

PROJECTS = os.path.expanduser("~/.claude/projects")


def current_session_uuid():
    files = glob.glob(os.path.join(PROJECTS, "*", "*.jsonl"))
    if not files:
        return None
    latest = max(files, key=os.path.getmtime)
    return os.path.splitext(os.path.basename(latest))[0]


def fmt(n):
    return f"{n:,}"


def main():
    sid = sys.argv[1] if len(sys.argv) > 1 else current_session_uuid()
    if not sid:
        print("Could not determine the current session.")
        return 1

    try:
        out = subprocess.run(
            ["npx", "ccusage@latest", "session", "--json"],
            capture_output=True, text=True, timeout=120,
        ).stdout
        data = json.loads(out)
    except Exception as e:
        print(f"Failed to run ccusage: {e}")
        return 1

    sessions = data.get("session", [])
    hit = next((s for s in sessions if s.get("period") == sid), None)
    if not hit:
        print(f"No ccusage data for session {sid[:8]} yet (index may lag) — retry at wrap-up.")
        return 1

    models = ", ".join(m.split("claude-")[-1] for m in hit.get("modelsUsed", []))
    print(f"Token cost breakdown — session {sid[:8]}")
    print(f"   models:       {models}")
    print(f"   input:        {fmt(hit['inputTokens'])}")
    print(f"   output:       {fmt(hit['outputTokens'])}")
    print(f"   cache create: {fmt(hit['cacheCreationTokens'])}")
    print(f"   cache read:   {fmt(hit['cacheReadTokens'])}")
    print(f"   total:        {fmt(hit['totalTokens'])} tokens")
    print(f"   cost (API-equivalent): ${hit['totalCost']:.2f}  (not a real bill on a flat subscription)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
