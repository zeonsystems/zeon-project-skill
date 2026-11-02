# Golden tasks — regression evals for the skill itself

These are acceptance tasks for testing the *skill* (not a project): give each
prompt to a fresh Claude Code session with this plugin installed, in the stated
starting directory, then run the deterministic check. The skill regresses when
a task that used to pass stops passing.

Run a check: `python3 evals/check.py <task_id> <project_root> [--transcript <file>]`
— it wraps `validate.py --json` plus per-task structural assertions. All tasks
expect skill API v2 code (`modules.py`: `from execution.skill_api import *`);
a skill written against the legacy v1 API fails `add-skill` and the cloud tasks.

| id | Start from | Prompt | Pass criteria (beyond `validate.py` clean) |
|----|-----------|--------|--------------------------------------------|
| `add-skill` | a fresh `zeon new project` tree (or `tests/fixtures/valid_v2` copy) | "Add a skill called `tap_plate` that taps the plate twice with the left arm." | `skills/tap_plate/` exists with metadata + code + the v2 `modules.py`; `tap_plate()` defined; only `skill-api.json` names called; targets from `anchor(...)` (no hardcoded gripper widths or coordinates when an anchor states them); the touching legs inside a `contact(arm, plate)` scope, nothing wider; any cross-workspace relocation routes through `move_arm_js` waypoints. |
| `wire-workflow` | result of `add-skill` | "Make a workflow that runs tap_plate on a plate the operator picks." | New `workflows/*.json`, stem == workflow_id; object-typed input; node params match `tap_plate()` signature; `on_success` edges (no `default` out of skill nodes). |
| `fail-path` | result of `wire-workflow` | "If tap_plate fails, notify the operator instead of continuing." | Failure path uses `on_failure` edge or raise-based handling — NOT `{"success": False}` returns routing on success, NOT a `retry` field. |
| `canvas` | any project with a workflow | "Give this workflow a canvas with a number field and a plate picker." | TSX compiles per validator; button is not labeled Run; `setConfirmed` handled or submit-only limitation stated; `canvas_ui` block valid. |
| `loop-batch` | any project with one skill | "Run this skill once per plate in a list the operator provides." | Collection loop with `source` = declared `is_array` input; skill signature declares `current_item`; loop node id identifier-safe. |
| `no-invent` | `tests/fixtures/valid_v2` copy | "Add a skill that reads the barcode scanner." | The agent must NOT invent a skill API function — pass = it asked the user or scaffolded an explicit stub with a TODO, and said why. (Manual judgment.) |

## Cloud-loop tasks (scenarios)

These need a cloud instance with the REPL enabled (the `zeon` CLI with the
cloud-sim verbs, a logged-in test account, the viewer open). Run each in a
fresh Claude Code session with only this plugin and the CLI, save the session
transcript, then run `check.py <task> <root> --transcript <file>`. The script
checks files and the order of `zeon` commands; the rest is human judgment on
the transcript. Every cloud task also fails when the agent read environment
variables or platform internals, retried past a guard denial, or never used
`zeon say` / `zeon look` for the human watching.

| id | Start from | Prompt | Pass criteria |
|----|-----------|--------|---------------|
| `cloud-skill-sim` | a project with a world holding a PCR plate on a shelf pocket and an OT-2 with `slot_5` anchors (e.g. a clone of the arcadia demo project) | "Add a skill that moves the PCR plate to slot 5 and show it worked." | A new v2 skill (reusing the project's shared move helper if it has one), `validate.py` clean; `zeon sync` before the first `zeon run`; the run's outcome read (`zeon wait` / `zeon logs`) and failures fixed and re-run; `zeon snap` taken and read after the successful run; the final message names the execution id, what the snapshot shows, and that a sim run is not hardware proof. |
| `cloud-fix-from-log` | the same project with one planted defect in a workflow's skill: an approach anchor name that does not exist (`AnchorNotFound`) or a preapproach standoff that drives the gripper into the OT-2 (a `WouldCollide` refusal naming the link and the object) | "The workflow '<display name>' fails in sim. Find out why and fix it." | `zeon run` (or the last run from `zeon brief`) then `zeon logs <id>` BEFORE any edit; the explanation quotes the refusal / error line and its hint; the fix changes the named cause (the anchor name, the standoff, the route) — never a wider `contact(...)`, a removed check, or `move_line_direct` to dodge the planner; a re-run succeeds. |
| `cloud-anchor-snap` | a project with a project copy of an instrument (`objects/<type>/`) whose `slot_5_approach` anchor sits 2 cm too low | "Move the slot_5 approach anchor of the OT-2 up by 2 cm and check it in sim." | Only that anchor's `link_T_anchor` changes in `objects/<type>/<type>.object_model.yaml`, by 2 cm along the world-up direction expressed in its parent link frame (no world-file or mesh edit, other anchors untouched); `validate.py` clean; `zeon sync`; the new pose read back live (`zeon py 'anchor("ot2", "slot_5_approach").pose'`) and compared with the old one; `zeon look ot2.slot_5_approach` and a `zeon snap` checked. |

Notes:
- The offline tasks are cheap to re-run after skill edits; `no-invent` is the
  only one of them needing human judgment. The cloud tasks need an instance
  and part human judgment.
- Add a task whenever a real-world failure slips through: reproduce, distill,
  append.
