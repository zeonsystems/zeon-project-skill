# Flow: refactor (rename, version bump, cross-file changes)

Tier-3 operations — they touch multiple files and can break cross-references. **Always show the full change plan up front and require explicit user confirmation before touching anything.** Apply changes atomically when possible (all-or-nothing).

## When to route here

- Renaming a skill / workflow / world / object.
- Bumping a workflow's or skill's `version`.
- Promoting a workflow (e.g. `pick_v1` → `pick`, dropping the version suffix).
- Any operation that touches more than one file or that the validator depends on for consistency.

## Workflow rename — worked example

User: "Rename my workflow `pick_v2` to `pick`."

### Step 1 — Discovery

Find every reference to the old id. Run:

```bash
# Files that reference the old workflow_id, in JSON / YAML / TSX / Python.
grep -RIn --include='*.json' --include='*.yaml' --include='*.tsx' --include='*.py' -F 'pick_v2' .
```

(Use the `Grep` tool with `pattern: "pick_v2"`.)

Known places to check:

| Where | What |
|---|---|
| `workflows/pick_v2.json` | The file itself. Filename + `workflow_id` field + node ids (which embed the workflow_id) + edge `from_node`/`to_node` fields. |
| `project.json` | `active_workflow` field. |
| `canvas/pick_v2_screen.tsx` (or similar) | The canvas referenced by `canvas_ui.source_ref`. |
| `canvas/*.tsx` | Hardcoded component names or workflow ids inside any canvas. |
| Other workflow files | Workflows rarely reference each other, but check `parameters` blobs for `{"$workflow": ...}` shapes if present. |
| Skills | Skills shouldn't reference workflow ids; if one does, it's an antipattern — surface it. |

### Step 2 — Change plan

Compute the full plan **before** writing anything.

**First check what node-ID convention the workflow uses.** The scaffold's canonical form is short, semantic names (`start`, `grab`, `end`). Some workflows use a `<role>_<index>` form (`start_0`, `platefuge_1`, `end_2`). A small number embed the workflow id (`start_<workflow>_0`). Open the workflow JSON and inspect a few `node_id` values — **only rewrite node IDs if the workflow id appears inside them**. If they're already short or just role+index, leave them alone (renaming the workflow doesn't require renaming nodes that don't carry the workflow id).

Reference `references/naming-rules.md` for the canonical timestamp format when bumping `updated_at` (ISO-8601 with timezone, e.g. `2026-05-19T12:00:00.000Z`).

Show the plan to the user as a structured list:

```
Refactor plan: rename workflow `pick_v2` → `pick`

File renames:
  workflows/pick_v2.json → workflows/pick.json
  canvas/pick_v2_screen.tsx → canvas/pick_screen.tsx   (because canvas_ui.source_ref currently points at this)

Edits (after rename):
  workflows/pick.json
    - workflow_id:  "pick_v2" → "pick"
    - canvas_ui.source_ref: "canvas/pick_v2_screen.tsx" → "canvas/pick_screen.tsx"
    - updated_at: bumped to <now>
    - simulation_validated: reset to false (structural change)
    - node_ids: UNCHANGED — the workflow uses short ids (`start`, `grab`, `end`), no
      workflow_id substring to rewrite. If your workflow uses ids like
      `start_pick_v2_0`, then those would need to be rewritten and the edges
      pointing at them updated — list each substitution explicitly.

  project.json
    - active_workflow: "pick_v2" → "pick"
    - updated_at: bumped

  canvas/pick_screen.tsx (after rename)
    - export default function PickV2Screen() → PickScreen()   (optional; component names are cosmetic)

Risks:
  - The display `name` field on the workflow is currently "Pick v2". I'm NOT changing it — only ids. Want me to update the display name too? (yes/no)
  - Any historical run logs that reference `pick_v2` will not be updated.

Apply this plan?
```

### Step 3 — Confirmation

Wait for an unambiguous "yes" / "apply" / "ship it". On "no" or any reservation, ask what to change and re-compute.

### Step 4 — Atomic application

For multi-file changes, apply in an order that minimises the time the project is broken:

1. Update the **referenced** files first (`canvas_ui.source_ref` in the workflow, `active_workflow` in project.json).

   Wait — order matters: if we update `project.json.active_workflow` to `pick` *before* renaming the workflow file, the project briefly references a missing file. The safer order is:

   1. Rename `canvas/pick_v2_screen.tsx` → `canvas/pick_screen.tsx`.
   2. Rename `workflows/pick_v2.json` → `workflows/pick.json`.
   3. Edit `workflows/pick.json`: fix `workflow_id`, node ids, edge from/to, `canvas_ui.source_ref`, `updated_at`, `simulation_validated: false`.
   4. Optionally edit `canvas/pick_screen.tsx`: rename the component.
   5. Edit `project.json`: update `active_workflow`, bump `updated_at`.

Apply steps 1-5 sequentially. On any failure, stop and report exactly what was done. **Do not try to roll back automatically** — show the user the current state so they can decide.

### Step 5 — Validate

Run `scripts/validate_project.py`. Show output. Errors here mean the refactor broke something; investigate together.

## Version bump

For a skill or workflow `version: "1.0.0"` → `version: "1.1.0"`:

1. Read the file.
2. Diff: only `version` and `updated_at` change.
3. For workflows, also reset `simulation_validated: false` and clear `simulation_result` / `last_simulation_timestamp`.
4. Show diff, confirm, apply.
5. Validate.

No cross-file changes typically needed for version bumps unless `project.json` or another file pins to a specific version (uncommon in this codebase).

## Skill rename

Same shape as workflow rename:

| Place | Edit |
|---|---|
| `skills/<old>/` | Rename folder to `skills/<new>/`. |
| `skills/<new>/metadata.yaml` | `skill_id` field. Also reflect the new name in the leading `# Skill: <name>` comment. |
| `skills/<new>/robotic_code.py` | The function name (`def <new>(...)`). Apply `_py_identifier` (dashes → underscores). |
| Every workflow JSON | Find `node.skill_id == "<old>"` and update. |
| Every super-skill that imports the renamed skill | `from <old>.robotic_code import <old>` → `from <new>.robotic_code import <new>`. |

The discovery step uses `Grep` for both `"skill_id": "<old>"` (JSON) and `from <old>.robotic_code` (Python).

## Object rename

| Place | Edit |
|---|---|
| `objects/<old>/` | Rename folder to `objects/<new>/`. |
| `objects/<new>/<old>.urdf` | Rename file to `<new>.urdf`. |
| `objects/<new>/<old>.object_model.yaml` | Rename file to `<new>.object_model.yaml`. |
| `objects/<new>/<new>.urdf` | Update `<robot name="<old>">` → `<robot name="<new>">`. |
| `objects/<new>/<new>.object_model.yaml` | Update `urdf: <old>.urdf` → `urdf: <new>.urdf`. |
| Every world's `world_state.json` | Find `yaml_path` / `file_path` ending in `/<old>/<old>.object_model.yaml` (or `.obj`) and update. |
| Every workflow's `objects[].mesh_type` | Update if `<old>` matches. |

## World rename

| Place | Edit |
|---|---|
| `worlds/<old>/` | Rename folder to `worlds/<new>/`. |
| `worlds/<new>/world_state.json` | `metadata.name` field. |
| `project.json` | `active_world` field. |

If `.bin` / `.npz` files are present in the world folder, they get moved with the folder rename — no internal edits needed.

## Canvas rename

| Place | Edit |
|---|---|
| `canvas/<old>.tsx` | Rename file to `canvas/<new>.tsx`. |
| `canvas/<new>.tsx` | Optionally update the React component name (`export default function ...`). Cosmetic only — no runtime effect. |
| The owning workflow | `canvas_ui.source_ref` → `canvas/<new>.tsx`. Bump `canvas_ui.version`. |

## Sibling versions (e.g. v1 still exists)

If the user renames `<x>_v2` → `<x>` while `<x>_v1` still exists, ask before doing anything to `_v1`. Default: leave it untouched (historical reference). Possible follow-ups the user might want:

- Leave `_v1` alone. (Default.)
- Bump `_v1` to `_v1_legacy` to reduce confusion.
- Delete `_v1` entirely.

These are all separate T3 operations — never bundle.

## Don't

- Don't auto-rename without showing the plan. Refactors are T3 — full ceremony.
- Don't claim atomicity if the filesystem doesn't support it. Apply in an order that keeps the project as close to consistent as possible at every step.
- Don't update human-readable `name` fields when only renaming an id. Ask if the user wants the display label updated separately.
- Don't touch `data/runs/` historical archives. They're snapshots; they were correct at their timestamp.
- Don't try to roll back automatically on partial failure. Surface the state and let the user decide.
- Don't bundle unrelated issues found during refactor discovery (off-spec edge IDs, missing files, mismatched URDF names). Flag them as separate follow-ups; the user picks the order.

## After every refactor

- Re-run `scripts/validate_project.py`. Surface output.
- Suggest commit groupings: one commit for the rename, separate commit for any "follow-up" cleanup (display name, version bump). Per user instruction, the skill does NOT commit — only suggests.
