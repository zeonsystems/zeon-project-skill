#!/usr/bin/env python3
"""Deterministic checks of an agent session's ORDER of actions, for the golden
tasks in evals/README.md that are about the agent loop rather than the files.

Usage: python3 evals/check_transcript.py <task_id> <transcript.jsonl>
Exit 0 = pass, 1 = fail (reasons printed), 2 = usage error.

The transcript is a Claude Code session JSONL (one JSON object per line). Every
`tool_use` block anywhere in a line is read in order: a Bash call contributes
its `command`, a Write / Edit / MultiEdit / NotebookEdit call the `file_path`
it changed. Nothing else is interpreted.
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def _tool_uses(node):
    if isinstance(node, dict):
        if node.get("type") == "tool_use":
            yield node
        for v in node.values():
            yield from _tool_uses(v)
    elif isinstance(node, list):
        for v in node:
            yield from _tool_uses(v)


def events(path: Path) -> list[tuple[str, str]]:
    """[(kind, value)] in order: ("cmd", <one zeon command>) or ("edit", <file path>)."""
    out: list[tuple[str, str]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        for tu in _tool_uses(obj):
            inp = tu.get("input") or {}
            if tu.get("name") == "Bash":
                # one entry per `zeon ...` invocation in a compound command
                for part in re.split(r"&&|\|\||;|\n", str(inp.get("command") or "")):
                    part = part.strip()
                    m = re.search(r"(?:^|\s)(zeon\s.*)$", part)
                    if m:
                        out.append(("cmd", m.group(1).strip()))
            elif tu.get("name") in EDIT_TOOLS:
                fp = inp.get("file_path") or inp.get("notebook_path")
                if fp:
                    out.append(("edit", str(fp)))
    return out


def _argv(cmd: str) -> list[str]:
    try:
        argv = shlex.split(cmd)
    except ValueError:
        argv = cmd.split()
    # drop global flags before the verb (zeon --staging run ...)
    return [a for i, a in enumerate(argv) if not (i == 1 and a.startswith("--"))]


def verb(cmd: str) -> str:
    argv = _argv(cmd)
    return argv[1] if len(argv) > 1 else ""


def _rel(path: str) -> str:
    """The project-relative tail of a path (from skills/, workflows/, worlds/, canvas/ ...)."""
    m = re.search(r"(?:^|/)((?:skills|workflows|worlds|canvas|objects|inputs|data)/.*)$", path)
    return m.group(1) if m else path


PUSHES = {"sync", "push"}


def check_view_canvas(ev, errs):
    """`zeon open --canvas W` is given only after the canvas / workflow edits were pushed."""
    opens = [i for i, (k, v) in enumerate(ev) if k == "cmd" and verb(v) == "open" and "--canvas" in v]
    if not opens:
        errs.append("no `zeon open --canvas` link was given")
        return
    last = opens[-1]
    edits = [i for i, (k, v) in enumerate(ev[:last]) if k == "edit" and _rel(v).startswith(("canvas/", "workflows/"))]
    if edits:
        pushed = any(k == "cmd" and verb(v) in PUSHES for k, v in ev[edits[-1] + 1:last])
        if not pushed:
            errs.append("canvas/workflow edits were not pushed (`zeon sync` / `zeon push`) before `zeon open --canvas`")


def check_view_workflow(ev, errs):
    """`zeon open --workflow W` follows a push of the last workflow edit."""
    opens = [i for i, (k, v) in enumerate(ev) if k == "cmd" and verb(v) == "open" and "--workflow" in v]
    if not opens:
        errs.append("no `zeon open --workflow` link was given")
        return
    last = opens[-1]
    edits = [i for i, (k, v) in enumerate(ev[:last]) if k == "edit" and _rel(v).startswith("workflows/")]
    if edits and not any(k == "cmd" and verb(v) in PUSHES for k, v in ev[edits[-1] + 1:last]):
        errs.append("workflow edits were not pushed before `zeon open --workflow`")


def check_run_series(ev, errs):
    """Two or more `zeon run` of one name with no skill-code edit between the first and the last
    (an edit to skills/**/*.py invalidates the plan cache mid-series)."""
    runs: dict[str, list[int]] = {}
    for i, (k, v) in enumerate(ev):
        if k == "cmd" and verb(v) == "run":
            argv = _argv(v)
            name = next((a for a in argv[2:] if not a.startswith("-")), "")
            runs.setdefault(name, []).append(i)
    series = {n: idx for n, idx in runs.items() if len(idx) >= 2}
    if not series:
        errs.append("no series (two or more `zeon run` of the same name) found")
        return
    for name, idx in series.items():
        bad = [_rel(v) for k, v in ev[idx[0]:idx[-1]] if k == "edit"
               and _rel(v).startswith("skills/") and _rel(v).endswith(".py")]
        if bad:
            errs.append(f"skill code edited inside the `zeon run {name}` series ({', '.join(sorted(set(bad)))}): "
                        "every edited skill's plans are solved again")


def check_pull_first(ev, errs):
    """Before the first edit to a world or workflow the human may have changed in the app, the cloud
    copy was pulled (`zeon pull` or `zeon sync`)."""
    first = next((i for i, (k, v) in enumerate(ev) if k == "edit"
                  and _rel(v).startswith(("worlds/", "workflows/"))), None)
    if first is None:
        errs.append("no world or workflow edit found")
        return
    if not any(k == "cmd" and verb(v) in {"pull", "sync", "clone"} for k, v in ev[:first]):
        errs.append("edited a world/workflow before `zeon pull` / `zeon sync`: the human's app edits would conflict")


def check_run_after_push(ev, errs):
    """Every `zeon run` comes after a push of the edits made before it (the instance runs the pushed copy)."""
    runs = [i for i, (k, v) in enumerate(ev) if k == "cmd" and verb(v) == "run"]
    if not runs:
        errs.append("no `zeon run` found")
        return
    for r in runs:
        edits = [i for i, (k, v) in enumerate(ev[:r]) if k == "edit"
                 and _rel(v).startswith(("skills/", "workflows/", "worlds/", "objects/"))]
        if edits and not any(k == "cmd" and verb(v) in PUSHES for k, v in ev[edits[-1] + 1:r]):
            errs.append(f"`{ev[r][1]}` ran without pushing the edits before it (the instance runs the pushed copy)")


HOLD_TOOLS = re.compile(r"\b(?:held|retry|skip|fail)\(|dev\.run_(?:status|retry|skip|fail|held)")


def check_no_hold_tools(ev, errs):
    """The agent does not reach for the team's hold tools (they are not the customer's)."""
    for k, v in ev:
        if k == "cmd" and verb(v) == "py" and HOLD_TOOLS.search(v):
            errs.append(f"used a hold / run-control tool: {v}")


CHECKS = {
    "view-canvas": check_view_canvas,
    "view-workflow": check_view_workflow,
    "run-series": check_run_series,
    "pull-first": check_pull_first,
    "run-after-push": check_run_after_push,
    "no-hold-tools": check_no_hold_tools,
}


def run(task: str, transcript: Path) -> list[str]:
    errs: list[str] = []
    CHECKS[task](events(transcript), errs)
    return errs


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in CHECKS:
        print(f"usage: check_transcript.py <{'|'.join(CHECKS)}> <transcript.jsonl>", file=sys.stderr)
        return 2
    errs = run(argv[1], Path(argv[2]))
    if errs:
        print(f"FAIL {argv[1]}:")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"PASS {argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
