#!/usr/bin/env python3
"""Deterministic checks for the golden tasks in evals/README.md.

Usage: python3 evals/check.py <task_id> <project_root>
Exit 0 = pass, 1 = fail (reasons printed), 2 = usage error.
"""

from __future__ import annotations

import ast
import json
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


def check_wire_workflow(root: Path, errs: list[str]) -> None:
    flows = [w for w in _workflows(root) if w.get("workflow_id") not in {"pipette_demo", "demo_flow"}]
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


CHECKS = {
    "add-skill": check_add_skill,
    "wire-workflow": check_wire_workflow,
    "fail-path": check_fail_path,
    "canvas": check_canvas,
    "loop-batch": check_loop_batch,
}


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in set(CHECKS) | {"no-invent"}:
        print(f"usage: check.py <{'|'.join([*CHECKS, 'no-invent'])}> <project_root>",
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
