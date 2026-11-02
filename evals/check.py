#!/usr/bin/env python3
"""Deterministic checks for the golden tasks in evals/README.md.

Usage: python3 evals/check.py <task_id> <project_root> [--transcript <file>]
Exit 0 = pass, 1 = fail (reasons printed), 2 = usage error.

The cloud-loop tasks (cloud-*) also read the session transcript: a Claude Code
JSONL transcript or any text log of the shell commands the agent ran. Their
checks cover what is decidable from files and the command sequence; the rest
of their pass criteria is human judgment (evals/README.md).
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VALIDATE = REPO / "skills" / "zeon-projects" / "scripts" / "validate.py"


def validator(root: Path) -> dict:
    proc = subprocess.run([sys.executable, str(VALIDATE), str(root), "--json"],
                          capture_output=True, text=True)
    return json.loads(proc.stdout)


def _workflows(root: Path) -> list[dict]:
    out = []
    for p in (root / "workflows").glob("*.json"):
        try:
            out.append({"path": p, **json.loads(p.read_text())})
        except json.JSONDecodeError:
            pass
    return out


def _uses_v2(skill_dir: Path, errs: list[str]) -> None:
    """The skill imports the skill API v2 (directly or via modules.py), never v1."""
    texts = [p.read_text() for p in (skill_dir / "modules.py", skill_dir / "robotic_code.py") if p.is_file()]
    blob = "\n".join(texts)
    if "execution.execution_functions" in blob:
        errs.append(f"{skill_dir.name}: imports the legacy v1 API (execution.execution_functions)")
    if "execution.skill_api" not in blob:
        errs.append(f"{skill_dir.name}: no skill API v2 import (modules.py: from execution.skill_api import *)")


def check_add_skill(root: Path, errs: list[str]) -> None:
    d = root / "skills" / "tap_plate"
    if not d.is_dir():
        errs.append("skills/tap_plate/ missing")
        return
    code = d / "robotic_code.py"
    if not code.is_file():
        errs.append("robotic_code.py missing")
        return
    tree = ast.parse(code.read_text())
    if not any(isinstance(n, ast.FunctionDef) and n.name == "tap_plate" for n in tree.body):
        errs.append("tap_plate() not defined at top level")
    _uses_v2(d, errs)


def check_wire_workflow(root: Path, errs: list[str]) -> None:
    flows = [w for w in _workflows(root) if w.get("workflow_id") not in {"pipette_demo", "demo_flow", "plate_flow"}]
    if not flows:
        errs.append("no new workflow found")
        return
    wf = flows[0]
    if not any(i.get("type") == "object" for i in wf.get("inputs", [])):
        errs.append("no object-typed input")
    for e in wf.get("edges", []):
        fr = next((n for n in wf.get("nodes", []) if n.get("node_id") == e.get("from_node")), {})
        if fr.get("type") == "skill" and (e.get("condition") or {}).get("type") == "default":
            errs.append(f"default edge out of skill node {fr.get('node_id')!r}")


def check_fail_path(root: Path, errs: list[str]) -> None:
    for wf in _workflows(root):
        for n in wf.get("nodes", []):
            if n.get("type") == "skill" and "retry" in n:
                errs.append(f"{wf['path'].name}: retry field used (runtime no-op)")
    has_failure_edge = any(
        (e.get("condition") or {}).get("type") == "on_failure"
        for wf in _workflows(root) for e in wf.get("edges", []))
    if not has_failure_edge:
        errs.append("no on_failure edge found (and no in-skill escalation asserted)")


def check_canvas(root: Path, errs: list[str]) -> None:
    tsx = list((root / "canvas").glob("*.tsx")) if (root / "canvas").is_dir() else []
    if not tsx:
        errs.append("no canvas TSX found")
        return
    content = max(tsx, key=lambda p: p.stat().st_mtime).read_text()
    if ">Run<" in content:
        errs.append("submit button labeled 'Run' — submit stages, it does not run")


def check_loop_batch(root: Path, errs: list[str]) -> None:
    found = False
    for wf in _workflows(root):
        inputs = {i.get("name"): i for i in wf.get("inputs", [])}
        for n in wf.get("nodes", []):
            if n.get("type") == "loop" and (n.get("loop") or {}).get("type") == "collection":
                found = True
                src = n["loop"].get("source")
                inp = inputs.get(src)
                if not inp:
                    errs.append(f"loop source {src!r} not a declared input")
                elif not (inp.get("is_array") or inp.get("isArray")):
                    errs.append(f"loop source {src!r} is not is_array")
    if not found:
        errs.append("no collection loop found")


# ---------------------------------------------------------------------------
# cloud-loop tasks: files + the command sequence in the transcript
# ---------------------------------------------------------------------------

_ZEON_CMD = re.compile(r"\bzeon\s+(sync|py|run|wait|logs|snap|brief|say|look|open)\b")


def _commands(transcript: Path | None) -> list[str]:
    """The zeon verbs the agent ran, in order (best effort over any text log)."""
    if transcript is None or not transcript.is_file():
        return []
    return [m.group(1) for m in _ZEON_CMD.finditer(transcript.read_text(errors="replace"))]


def _transcript_text(transcript: Path | None) -> str:
    return transcript.read_text(errors="replace") if transcript and transcript.is_file() else ""


def _loop_hygiene(transcript: Path | None, errs: list[str]) -> list[str]:
    cmds = _commands(transcript)
    if not cmds:
        errs.append("no transcript (or no zeon commands in it): pass --transcript <file>")
        return cmds
    text = _transcript_text(transcript)
    if "repl_guard_denied" in text and text.count("repl_guard_denied") > 1:
        errs.append("more than one guard denial: the agent retried past a denial instead of "
                    "rewriting with the skill API")
    if re.search(r"os\.environ|getenv|/app/services|/app/libraries|inspect\.getsource|__subclasses__", text):
        errs.append("transcript shows an attempt to read environment / platform internals")
    if "say" not in cmds and "look" not in cmds:
        errs.append("never used zeon say / zeon look: the human watching the viewer was not kept informed")
    return cmds


def _new_skills(root: Path) -> list[Path]:
    known = {"pipette_demo", "demo_skill", "plate_to_stand"}
    sdir = root / "skills"
    return [d for d in sdir.iterdir() if d.is_dir() and d.name not in known] if sdir.is_dir() else []


def check_cloud_skill_sim(root: Path, errs: list[str], transcript: Path | None = None) -> None:
    skills = [d for d in _new_skills(root) if (d / "robotic_code.py").is_file()]
    if not skills:
        errs.append("no skill with robotic_code.py found")
    for d in skills:
        _uses_v2(d, errs)
    cmds = _loop_hygiene(transcript, errs)
    if cmds:
        if "sync" not in cmds or "run" not in cmds or cmds.index("sync") > cmds.index("run"):
            errs.append("expected zeon sync before the first zeon run")
        if "snap" not in cmds:
            errs.append("never looked at the result (zeon snap)")


def check_cloud_fix_from_log(root: Path, errs: list[str], transcript: Path | None = None) -> None:
    cmds = _loop_hygiene(transcript, errs)
    if cmds:
        if "logs" not in cmds:
            errs.append("never read the failing run's log (zeon logs <id>)")
        elif "run" in cmds and cmds.index("logs") > max(i for i, c in enumerate(cmds) if c == "run"):
            errs.append("no re-run after reading the log: the fix was not verified in sim")
        if cmds.count("run") < 1:
            errs.append("never re-ran the workflow after the fix")
    for py in root.glob("skills/**/*.py"):
        src = py.read_text(errors="replace")
        if re.search(r"parts\s*=\s*\(?\s*[\"']arm[\"']", src) and "contact(" in src:
            errs.append(f"{py.relative_to(root)}: a contact scope with parts='arm' — a widened "
                        "allowance is not a fix for a refusal (check by hand)")


def check_cloud_anchor_snap(root: Path, errs: list[str], transcript: Path | None = None) -> None:
    models = list(root.glob("objects/*/*.object_model.yaml"))
    if not models:
        errs.append("no project object model: the anchor edit must be in objects/<type>/")
    cmds = _loop_hygiene(transcript, errs)
    if cmds:
        if "sync" not in cmds:
            errs.append("the anchor edit was never synced to the instance (zeon sync)")
        if "snap" not in cmds:
            errs.append("never checked the moved anchor with zeon snap")
        if "py" not in cmds and "look" not in cmds:
            errs.append("never read the anchor back from the live world (zeon py anchor(...).pose / zeon look)")
    text = _transcript_text(transcript)
    if re.search(r"world\.world", text) and re.search(r"(Edit|Write).{0,200}world\.world", text):
        errs.append("edited a world file; an anchor move belongs in the object model")


CLOUD_CHECKS = {
    "cloud-skill-sim": check_cloud_skill_sim,
    "cloud-fix-from-log": check_cloud_fix_from_log,
    "cloud-anchor-snap": check_cloud_anchor_snap,
}


CHECKS = {
    "add-skill": check_add_skill,
    "wire-workflow": check_wire_workflow,
    "fail-path": check_fail_path,
    "canvas": check_canvas,
    "loop-batch": check_loop_batch,
}


def main(argv: list[str]) -> int:
    transcript = None
    if "--transcript" in argv:
        i = argv.index("--transcript")
        if i + 1 >= len(argv):
            print("--transcript needs a file", file=sys.stderr)
            return 2
        transcript = Path(argv[i + 1]).resolve()
        argv = argv[:i] + argv[i + 2:]
    tasks = [*CHECKS, *CLOUD_CHECKS, "no-invent"]
    if len(argv) != 3 or argv[1] not in tasks:
        print(f"usage: check.py <{'|'.join(tasks)}> <project_root> [--transcript <file>]",
              file=sys.stderr)
        return 2
    task, root = argv[1], Path(argv[2]).resolve()
    if task == "no-invent":
        print("no-invent requires human judgment: did the agent refuse to invent an "
              "execution function and either ask or scaffold an explicit TODO stub?")
        return 0

    errs: list[str] = []
    result = validator(root)
    if not result["ok"]:
        errs.append(f"validate.py reports {len(result['errors'])} error(s)")
    if task in CLOUD_CHECKS:
        CLOUD_CHECKS[task](root, errs, transcript)
    else:
        CHECKS[task](root, errs)

    if errs:
        print(f"FAIL {task}:")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"PASS {task}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
