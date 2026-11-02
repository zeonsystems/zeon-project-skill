#!/usr/bin/env python3
"""Regression tests for the zeon-projects skill's deterministic tooling.

Run from anywhere:  python3 tests/run_tests.py

- compiles every bundled script
- sanity-checks the vendored skill API manifests (v2 skill-api.json, legacy v1
  execution-functions.json)
- validates fixtures/valid_v2  → zero errors AND zero warnings (skill API v2)
- validates fixtures/valid_min → zero errors; warns on its legacy v1 import
- validates fixtures/broken    → every expected defect must be reported
"""

from __future__ import annotations

import json
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
    "the loader cannot tell which object model to load",
    # skills
    "description missing",                      # metadata: catalog-fatal description
    "parameters[0].name must be snake_case",
    "parameters[0].type invalid",
    "phantom/duplicate skill",                  # stray nested metadata.yaml
    "imports 'imaginary_teleport'",             # unknown platform import
    "but bad_skill/modules.py does not exist",  # .modules import w/o shim
    "collides with an engine-reserved state key",  # param named skill_result
    "arm must be exactly 'left_arm' or 'right_arm'",   # v1 arm literal
    "is a retired v1 verb",                     # v1 move_arm raises on the current platform
    "imports the legacy skill API v1",          # v1 import (warning)
    "unknown keyword",                          # move_arm(..., turbo=True)
    "missing required argument(s)",             # move_arm(arm=...) only
    "safe=False",
    "invented_function_xyz",                    # NameError lint
    "never returns a dict with a 'success' key",
    "passes a display name",                    # live_state keyed by instance id
    # skills: skill API v2 (bad_v2_skill)
    "anchor 'no_such_anchor' not found",        # anchor(obj, name) vs the object model
    "move_arm(..., position=",                  # v1 keyword on the v2 verb
    "arm must be 'left' or 'right'",            # v2 arm literal
    "place_object() is deprecated",             # deprecated v2 name (warning)
    "'deg' is not star-exported",               # by-name-only v2 import used via star
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
    "UUID-shaped defaultValue",
    # canvas
    "filename stem must match",
    "import of 'axios'",
    # input presets
    "inputs/bad.json",                          # malformed preset (platform skips silently)
    "matches no declared workflow input",
    # objects: motions
    "parent_link 'nonexistent_link' is not a URDF link",
    "needs at least two keyposes",
    "goes backwards",
    "gripper=-0.01 is negative",
    "no description",                           # motion without a description (warning)
    # objects: tag collections
    "carries both inline tag anchors",          # inline tag_<id> + tag_collections/
    "must be exactly 'tag_collection/v1'",
    "'apriltag_36h11' is the only accepted value",
    "size_m -0.02 must be a positive number",
    "tag 3: link_T_tag needs xyz and wxyz",
    "the loader ignores this file",             # non-conforming unit handle (warning)
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
    manifest = json.loads((SKILL / "references" / "skill-api.json").read_text())
    fns = manifest.get("functions", {})
    if manifest.get("api") != "v2":
        fail("skill-api.json is not the v2 manifest")
    for required in ("move_arm", "move_arm_js", "move_relative", "set_gripper", "anchor",
                     "attach", "release", "contact", "Pose", "is_sim_mode", "pause_for_user",
                     "SkillError", "WouldCollide"):
        if required not in fns:
            fail(f"v2 manifest missing {required!r}")
    move_arm = fns["move_arm"]["signature"]
    if [p["name"] for p in move_arm[:2]] != ["arm", "target"] or \
            any(p["kind"] != "keyword_only" for p in move_arm[2:]):
        fail("v2 move_arm is not (arm, target, *, ...) — regenerate and re-review")
    if "safe" in {p["name"] for p in move_arm}:
        fail("manifest claims move_arm has a 'safe' parameter — regenerate and re-review")
    for gone in ("snap_object_to_world_pose", "play_object_motion", "get_arm_pose",
                 "load_object_anchor"):
        if gone in fns:
            fail(f"v2 manifest lists {gone!r}, which v2 does not export")
    if "deg" not in manifest.get("importable_by_name", {}):
        fail("v2 manifest lacks importable_by_name (deg, mm, Tolerance, ...)")
    print(f"ok: v2 manifest has {len(fns)} names ({manifest.get('source')})")

    legacy = json.loads((SKILL / "references" / "execution-functions.json").read_text())
    lfns = legacy.get("functions", {})
    if legacy.get("api") != "v1" or not lfns.get("move_arm", {}).get("retired"):
        fail("execution-functions.json is not the v1 manifest with retired verbs marked")
    print(f"ok: v1 manifest has {len(lfns)} names "
          f"({sum(1 for v in lfns.values() if v.get('retired'))} retired)")

    # 3a. Valid v2 fixture → zero errors, zero warnings.
    result = run_validator(FIXTURES / "valid_v2")
    if not result["ok"] or result["errors"] or result["warnings"]:
        fail("valid_v2 fixture should have zero errors and zero warnings, got:\n"
             + json.dumps(result["errors"] + result["warnings"], indent=2))
    print("ok: valid_v2 passes (0 warnings)")

    # 3b. Valid v1 (legacy) fixture → zero errors; the v1 import is a warning.
    result = run_validator(FIXTURES / "valid_min")
    if not result["ok"] or result["errors"]:
        fail("valid_min fixture should have zero errors, got:\n"
             + json.dumps(result["errors"], indent=2))
    flagged = [m for m in result["errors"] + result["warnings"]
               if "tipbox" in json.dumps(m) or "plate_from_workflow_input" in json.dumps(m)]
    if flagged:
        fail("objects with no objects/ copy in the project load from the mesh database "
             "and must not be flagged, got:\n" + json.dumps(flagged, indent=2))
    if not any("imports the legacy skill API v1" in w["msg"] for w in result["warnings"]):
        fail("valid_min (v1 import) should warn about the legacy skill API")
    print(f"ok: valid_min (legacy v1) passes ({len(result['warnings'])} warnings)")

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
    print(f"ok: broken fixture reports all {len(EXPECTED_BROKEN)} planted defects "
          f"({len(result['errors'])} errors, {len(result['warnings'])} warnings)")

    print("all tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
