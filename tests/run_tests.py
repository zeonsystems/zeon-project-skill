#!/usr/bin/env python3
"""Regression tests for the zeon-projects skill's deterministic tooling.

Run from anywhere:  python3 tests/run_tests.py

- compiles every bundled script
- validates fixtures/valid_min → must be OK with zero errors
- validates fixtures/broken   → every expected defect must be reported
- sanity-checks the vendored execution-function manifest
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
    # skills
    "description missing",                      # metadata: catalog-fatal description
    "parameters[0].name must be snake_case",
    "parameters[0].type invalid",
    "phantom/duplicate skill",                  # stray nested metadata.yaml
    "imports 'imaginary_teleport'",             # unknown platform import
    "but bad_skill/modules.py does not exist",  # .modules import w/o shim
    "collides with an engine-reserved state key",  # param named skill_result
    "arm must be exactly 'left_arm' or 'right_arm'",
    "unknown keyword",                          # move_arm(..., turbo=True)
    "missing required argument(s)",             # move_arm(arm=...) only
    "safe=False",
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
    "UUID-shaped defaultValue",
    # canvas
    "filename stem must match",
    "import of 'axios'",
    # input presets
    "inputs/bad.json",                          # malformed preset (platform skips silently)
    "matches no declared workflow input",
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
    for required in ("move_arm", "set_gripper", "load_object_anchor", "is_sim_mode",
                     "pause_for_user", "update_object_joint_config"):
        if required not in fns:
            fail(f"manifest missing {required!r}")
    move_arm_params = {p["name"] for p in fns["move_arm"]["signature"]}
    if "safe" in move_arm_params:
        fail("manifest claims move_arm has a 'safe' parameter — regenerate and re-review")
    print(f"ok: manifest has {len(fns)} functions ({manifest.get('source')})")

    # 3. Valid fixture → zero errors.
    result = run_validator(FIXTURES / "valid_min")
    if not result["ok"] or result["errors"]:
        fail("valid_min fixture should have zero errors, got:\n"
             + json.dumps(result["errors"], indent=2))
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
    print(f"ok: broken fixture reports all {len(EXPECTED_BROKEN)} planted defects "
          f"({len(result['errors'])} errors, {len(result['warnings'])} warnings)")

    print("all tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
