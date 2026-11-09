#!/usr/bin/env python3
"""Regression tests for the zeon-projects skill's deterministic tooling.

Run from anywhere:  python3 tests/run_tests.py

- compiles every bundled script
- validates fixtures/valid_min → must be OK with zero errors
- validates fixtures/broken   → every expected defect must be reported
- sanity-checks the vendored skill API v2 manifest
"""

from __future__ import annotations

import json
import re
import py_compile
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "zeon-projects"
VALIDATE = SKILL / "scripts" / "validate.py"
FIXTURES = REPO / "tests" / "fixtures"

# Substrings that must appear in the broken fixture's errors+warnings.
EXPECTED_BROKEN = [
    # worlds: an instance the loader cannot name (no metadata, no objects/ segment)
    "the loader cannot tell which object model to load",  # no metadata.type, no yaml_path
    "names it; the world cannot load",          # v2 manifest without its world.world
    # skills
    "description missing",                      # metadata: catalog-fatal description
    "parameters[0].name must be snake_case",
    "parameters[0].type invalid",
    "phantom/duplicate skill",                  # stray nested metadata.yaml
    "imports 'imaginary_teleport'",             # unknown platform import
    "but bad_skill/modules.py does not exist",  # .modules import w/o shim
    "collides with an engine-reserved state key",  # param named skill_result
    "an arm is 'left' or 'right'",              # move_arm("left_hand", ...)
    "unknown keyword",                          # move_arm(..., turbo=True)
    "missing required argument(s)",             # move_arm(arm=...) only
    "safe=False",
    "raises TcpSpeedOnFreeMove",                # tcp_speed on a free move_arm
    "speed is a fraction (0, 1]",               # v1-style speed=500
    "written against the v1 surface",           # legacy_skill: modules.py star-imports v1
    "play_object_motion() is a retired v1 verb",  # raises NotImplementedError
    "invented_function_xyz",                    # NameError lint
    "never returns a dict with a 'success' key",
    "passes a display name",                    # live_state keyed by instance id
    # workflows
    "!= filename stem",                         # workflow_id vs file
    "duplicate workflow_id",
    "no such input is declared",                # $input 'nope'
    "requires parameter 'count'",               # unbound required param
    "'volumn' is not in",                       # unknown node param key
    "'retry' on skill nodes is a runtime no-op",
    "conditional expressions support only",     # count < 5
    "names no declared workflow input",         # collection source
    "loop node_id 'fill-loop'",                 # identifier-unsafe loop id
    "'default' edge out of a skill node",
    # canvas
    "filename stem must match",
    "import of 'axios'",
    # input presets
    "inputs/bad.json",                          # malformed preset (platform skips silently)
    "matches no declared workflow input",
    # objects: motions.yaml (motions/1)
    "parent_link 'nonexistent_link' is not a URDF link",
    "needs at least two keyposes",
    "goes backwards",
    "gripper=-0.01 is negative",
    "no description",                           # motion without a description (warning)
    # objects: the object-model schema (the loader refuses the object)
    "unknown key 'motions'",                    # motions moved to motions.yaml
    "missing 'profile'",
    "the loader refuses tag anchors",            # tag_7 in the model
    "field 'grasp' was removed from the schema",
    "does not read as 'grasp: width",           # malformed grasp segment in a description
    # objects: a unit's tags.yaml (tag_calibration/3)
    "expected 'tag_calibration/3'",
    "'joints' must be {}",
    "is the only supported family",
    "nominal_size_m -0.02 must be a positive number",
    "tag_3: link_T_anchor needs xyz and wxyz",
    "the loader ignores this unit",             # non-conforming unit handle (warning)
    "no longer reads tag_collections/",         # legacy folder (warning)
    # project.json
    "active_workflow 'ghost_flow'",
]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def run_validator(root: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(VALIDATE), str(root), "--json"],
        capture_output=True, text=True,
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        fail(f"validator produced no JSON for {root}:\n{proc.stdout}\n{proc.stderr}")
        raise


def main() -> int:
    # 1. Everything compiles.
    for script in list((SKILL / "scripts").glob("*.py")) + list((SKILL / "scripts" / "dev").glob("*.py")):
        py_compile.compile(str(script), doraise=True)
    print(f"ok: {len(list((SKILL / 'scripts').rglob('*.py')))} scripts compile")

    # 2. Manifest sanity.
    manifest = json.loads((SKILL / "references" / "execution-functions.json").read_text())
    fns = manifest.get("functions", {})
    for required in ("move_arm", "move_arm_js", "move_relative", "set_gripper", "anchor",
                     "resolve", "contact", "attach", "release", "is_sim_mode",
                     "pause_for_user", "get_world_state"):
        if required not in fns:
            fail(f"manifest missing {required!r}")
    if "skill_api" not in manifest.get("source", ""):
        fail("manifest is not generated from execution.skill_api (skill API v2)")
    move_arm_params = {p["name"] for p in fns["move_arm"]["signature"]}
    if "safe" in move_arm_params:
        fail("manifest claims move_arm has a 'safe' parameter — regenerate and re-review")
    if "tcp_speed" not in move_arm_params or "straight_line" not in move_arm_params:
        fail("manifest move_arm lacks the v2 keywords straight_line / tcp_speed")
    if "move_arm" not in manifest.get("v1_retired", []):
        fail("manifest does not list the retired v1 motion verbs")
    print(f"ok: manifest has {len(fns)} functions ({manifest.get('source')})")

    # 3. Valid fixture → zero errors.
    result = run_validator(FIXTURES / "valid_min")
    if not result["ok"] or result["errors"]:
        fail("valid_min fixture should have zero errors, got:\n"
             + json.dumps(result["errors"], indent=2))
    flagged = [m for m in result["errors"] + result["warnings"]
               if "tipbox" in json.dumps(m) or "plate_from_workflow_input" in json.dumps(m)]
    if flagged:
        fail("objects with no objects/ copy in the project load from the mesh database "
             "and must not be flagged, got:\n" + json.dumps(flagged, indent=2))
    print(f"ok: valid_min passes ({len(result['warnings'])} warnings)")

    # 4. Broken fixture → every planted defect reported.
    result = run_validator(FIXTURES / "broken")
    blob = json.dumps(result["errors"] + result["warnings"])
    missing = [marker for marker in EXPECTED_BROKEN if marker not in blob]
    if missing:
        fail("broken fixture: expected defects not reported:\n  - "
             + "\n  - ".join(missing)
             + "\n\nvalidator output:\n" + json.dumps(result, indent=2))
    if result["ok"]:
        fail("broken fixture unexpectedly passed")
    # A declared string input passes through as is, UUID-shaped or not (bad_flow's 'items').
    if "UUID" in blob:
        fail("a UUID-shaped default on a declared string input must not be flagged")
    print(f"ok: broken fixture reports all {len(EXPECTED_BROKEN)} planted defects "
          f"({len(result['errors'])} errors, {len(result['warnings'])} warnings)")

    # 5. Agent-loop eval checker: each pass/fail transcript fixture gets its verdict.
    sys.path.insert(0, str(REPO / "evals"))
    import check_transcript  # noqa: E402

    tdir = FIXTURES / "transcripts"
    for task in check_transcript.CHECKS:
        for verdict in ("pass", "fail"):
            path = tdir / f"{task}.{verdict}.jsonl"
            if not path.is_file():
                fail(f"missing transcript fixture {path.name}")
            errs = check_transcript.run(task, path)
            if (verdict == "pass") == bool(errs):
                fail(f"check_transcript {task} on {path.name}: expected {verdict}, got {errs or 'pass'}")
    print(f"ok: transcript checks give the expected verdict on {2 * len(check_transcript.CHECKS)} fixtures")

    # 6. Skill text: the rules an agent acts on are stated, and nothing internal ships.
    text = {p.relative_to(REPO).as_posix(): p.read_text()
            for p in [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]}
    skill_md = text["skills/zeon-projects/SKILL.md"]
    required = {
        "SKILL.md": [
            "zeon up", "zeon run", "zeon open --workflow", "zeon open --canvas", "Confirm setup", "zeon up` first",
            "world_missing", "from_project", "64 MB", "data/runs/", ".runtime/", "metadata.json", "zeon pull",
            "plan cache", "top-level `skills/*.py`", "Stop is final", "ask_user_slack",
            "from execution.skill_api import *", '"left"', "public items plus your org",
        ],
        "references/agent-loop.md": ["every 3 s", "zeon up", "world_missing", "waiting_on_prompt"],
        "references/execution-model.md": ["410", "timeout counting", "source digest", "in memory N, read M"],
        "references/project-layout.md": ["64 MB", "run_log_", ".motion_plan_cache.pkl", "data/runs/"],
        "references/canvas.md": ["zeon open --canvas", "every 3 s", "no canvas editor"],
    }
    for rel, phrases in required.items():
        body = skill_md if rel == "SKILL.md" else text[f"skills/zeon-projects/{rel}"]
        missing = [ph for ph in phrases if ph not in body]
        if missing:
            fail(f"{rel} no longer states: {missing}")
    if len(skill_md.encode()) > 14_000:
        fail(f"SKILL.md is {len(skill_md.encode())} bytes; move detail into references/")
    # The skill ships to customers: no internal tools, team-only run controls, hosts, addresses or tokens.
    forbidden = [
        (r"\bzeonctl\b|\bzeon-dev\b|\breplmux\b", "internal tool"),
        (r"\bheld\(\)|dev\.run_|next_actions|control_state", "team-only run control"),
        (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "IP address"),
        (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", "email address"),
        (r"zat_[A-Za-z0-9]{6,}", "token"),
        (r"scratch/|\.claude/projects", "internal path"),
    ]
    for rel, body in text.items():
        for pattern, what in forbidden:
            m = re.search(pattern, body)
            if m:
                fail(f"{rel}: {what} {m.group(0)!r} must not ship in the skill")
    print(f"ok: skill text states the agent-loop rules and ships nothing internal ({len(text)} files)")

    print("all tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
