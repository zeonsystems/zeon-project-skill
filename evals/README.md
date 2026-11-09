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

## Agent-loop tasks — checked from the session transcript

These are about the ORDER of what the agent does with the `zeon` CLI, so the
check reads the session's Claude Code transcript (the `.jsonl` under
`~/.claude/projects/...`), not the project:
`python3 evals/check_transcript.py <task_id> <transcript.jsonl>`. Start each
from a cloned project with a signed-in CLI and a sim instance.

| id | Prompt | Pass criteria |
|----|--------|---------------|
| `view-canvas` | "Add a volume slider to this workflow's canvas and send me a link to check it." | `zeon open --canvas W` given after a `zeon sync` / `zeon push` that follows the last `canvas/` or `workflows/` edit; the reply tells the human to press Confirm setup again (manual). |
| `view-workflow` | "Add a second plate step to the workflow and show me the graph." | `zeon open --workflow W` after the workflow edit was pushed. |
| `run-series` | "Run tap_plate three times and tell me how long each run takes." | No edit to `skills/**/*.py` between the first and last `zeon run` of the series (an edit re-solves the plan cache); edits batched before. |
| `pull-first` | (the human first moves an object in the World Builder and saves) "Nudge the plate stand 2 cm toward the arm in the world file." | `zeon pull` or `zeon sync` before the first `worlds/` / `workflows/` edit. |
| `run-after-push` | "Fix the approach height in tap_plate and run it." | Every `zeon run` follows a push of the edits made before it. |
| `no-hold-tools` | (a workflow whose skill raises) "Run the workflow and get it to finish." | The agent reads `zeon logs`, fixes and re-runs; it never calls `held()`, `retry()`, `skip()`, `fail()` or `dev.run_*` in `zeon py`. |

`tests/fixtures/transcripts/` holds a passing and a failing transcript per task;
`tests/run_tests.py` runs the checker on them.

Notes:
- Tasks are cheap to re-run after skill edits; `no-invent` is the only one
  needing human judgment.
- Add a task whenever a real-world failure slips through: reproduce, distill,
  append.
