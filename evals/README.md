# Golden tasks — regression evals for the skill itself

These are acceptance tasks for testing the *skill* (not a project): give each
prompt to a fresh Claude Code session with this plugin installed, in the stated
starting directory, then run the deterministic check. The skill regresses when
a task that used to pass stops passing.

Run a check: `python3 evals/check.py <task_id> <project_root>` — it wraps
`validate.py --json` plus per-task structural assertions.

| id | Start from | Prompt | Pass criteria (beyond `validate.py` clean) |
|----|-----------|--------|--------------------------------------------|
| `add-skill` | a fresh `zeon new project` tree (or `tests/fixtures/valid_min` copy) | "Add a skill called `tap_plate` that taps the plate twice with the left arm." | `skills/tap_plate/` exists with metadata + code; `tap_plate()` defined; only manifest functions called; no hardcoded gripper widths when an anchor grasp block is available; any cross-workspace arm relocation routes through transition poses (`move_arm_js` waypoints), not a long free-space `move_arm`. |
| `wire-workflow` | result of `add-skill` | "Make a workflow that runs tap_plate on a plate the operator picks." | New `workflows/*.json`, stem == workflow_id; object-typed input; node params match `tap_plate()` signature; `on_success` edges (no `default` out of skill nodes). |
| `fail-path` | result of `wire-workflow` | "If tap_plate fails, notify the operator instead of continuing." | Failure path uses `on_failure` edge or raise-based handling — NOT `{"success": False}` returns routing on success, NOT a `retry` field. |
| `canvas` | any project with a workflow | "Give this workflow a canvas with a number field and a plate picker." | TSX compiles per validator; button is not labeled Run; `setConfirmed` handled or submit-only limitation stated; `canvas_ui` block valid. |
| `loop-batch` | any project with one skill | "Run this skill once per plate in a list the operator provides." | Collection loop with `source` = declared `is_array` input; skill signature declares `current_item`; loop node id identifier-safe. |
| `no-invent` | `tests/fixtures/valid_min` copy | "Add a skill that reads the barcode scanner." | The agent must NOT invent an execution function — pass = it asked the user or scaffolded an explicit stub with a TODO, and said why. (Manual judgment.) |

Notes:
- Tasks are cheap to re-run after skill edits; `no-invent` is the only one
  needing human judgment.
- Add a task whenever a real-world failure slips through: reproduce, distill,
  append.
