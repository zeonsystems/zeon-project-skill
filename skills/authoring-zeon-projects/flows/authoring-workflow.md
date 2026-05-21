# Flow: author a new workflow

A workflow is a single JSON file at `workflows/<workflow_id>.json` describing a graph of nodes (start, end, skill, conditional, loop) connected by edges. The on-disk format is the **Workflow** schema (not `ExecutionGraph`).

**Schemas**: `references/schema-workflow.md`, `references/naming-rules.md`. Examples: `examples/workflow-linear.md`, `examples/workflow-with-conditional.md`.

## Required information (interview)

Ask one at a time:

1. **What's the goal of the workflow?** (one-sentence summary)
2. **`workflow_id`** — snake_case, `^[a-z0-9_]+$`. The filename will be `workflows/<workflow_id>.json`.
3. **Display name** — human-friendly, may contain spaces and capitalization.
4. **What `inputs` does it take?** For each input, collect:
   - `name` (PascalCase or snake_case, starts with letter)
   - `type` (`string`, `int`, `float`, `object`, `structured`)
   - `is_array` (true/false)
   - `description` (optional but recommended)
   - `default_value` (optional)
5. **What's the sequence?** Walk through the high-level steps the user wants. Then map each step to:
   - A skill node (`skill_id` must exist at `skills/<id>/`).
   - A conditional node (if there's branching).
   - A loop node (if something repeats).
6. **For each skill node, which inputs / objects / literals feed each parameter?** Each parameter value is one of:
   - `{"$input": "<input_name>"}` — drawn from `inputs[]`.
   - `{"alias": "<obj_alias>", "offset": {"xyz": [..], "wxyz": [..]}}` — an `ObjectReference` to an entry in `objects[]`.
   - A literal (number, string, bool).
7. **Do you want a canvas?** If yes — note it for the canvas flow after this. If no, the platform auto-generates a form from `inputs`.
8. **Should it have an author?** Default to `user` if unspecified. The user can override.

## Building the graph

Skeleton for a linear N-skill workflow:

```
start → <skill_a> → <skill_b> → ... → end
```

Node IDs are short, semantic names — `start`, `end`, plus one per skill (`grab`, `move`, `drop`, ...). Disambiguate collisions with a suffix (`grab_a`, `grab_b`). Edge IDs follow `^e\d+$` — `e0`, `e1`, `e2`, ...

Edge conditions:
- From `start`: `condition.type = "default"`.
- Between regular skill nodes: `"on_success"`.
- For failure-handling branches: `"on_failure"`.
- From a `conditional` node: `"if_true"` + `"if_false"` (exactly 2 outgoing edges, enforced).
- For loops: `"loop_continue"` (body) + `"loop_complete"` (exit), exactly 2 outgoing.

## Generation

1. Run `scripts/invoke_scaffold.py item workflow <workflow_id>`. The script returns a starter file with the canonical on-disk format (`workflow_id`, `type`, nested `condition`, `e0`).
2. Decode the base64 content.
3. Overlay user-supplied content:
   - Top-level `name`, `description`, `version` (default `"1.0.0"`), `author`, `created_at`/`updated_at` (now, ISO-8601 ms).
   - `inputs[]` — one entry per user-specified input.
   - `nodes[]` — start + each skill / conditional / loop + end. Use short semantic IDs.
   - `edges[]` — wire them up per the user's sequence. Use `e0`, `e1`, etc.
   - Leave `objects: []` unless the user explicitly wants the legacy generic-object declarations.
4. Write `workflows/<workflow_id>.json` via `Write`.

## Modifying an existing workflow (T2)

If the user wants to add a node, change an edge, edit parameters, etc., follow the T2 ceremony from `develop-mode.md`:

1. Read the current file.
2. Compute the new file content.
3. Show the user a unified diff.
4. Wait for explicit confirmation.
5. Apply via `Edit` (precise) or `Write` (rewrite). Bump `updated_at`.
6. Reset `simulation_validated: false` and clear `simulation_result` / `last_simulation_timestamp` — any structural change invalidates prior simulation. Note this in the diff so the user sees it.

## Validation

1. `python3 -c "import json; json.load(open('workflows/<id>.json'))"` parses.
2. `scripts/validate_project.py` runs the structural checks (1 start, ≥1 end, valid types, edge ids match `edge_\d+`, etc.) plus skill cross-refs.
3. If errors, surface them to the user and fix before declaring done.

## Cross-reference checks

- Every `node.skill_id` for `type: "skill"` nodes must resolve to `skills/<skill_id>/`. If missing, ask the user whether to scaffold the skill (`authoring-skill.md`) or repoint the node.
- Every `parameters.*.$input` reference must match a name in `inputs[]`.
- Every `parameters.*.alias` reference (`ObjectReference`) must match an `alias` in `objects[]`.
- `canvas_ui.source_ref`, if set, must reference an existing `canvas/<id>.tsx`.

## Common mistakes

- Using `node_type` instead of `type`. **`ExecutionGraph` shape — wrong for disk.**
- Using `graph_id` instead of `workflow_id`. Same.
- Edge IDs like `edge_0`. Use `e0` — the scaffold's canonical form.
- Long node IDs like `start_<workflow>_0`. Use short semantic names (`start`, `grab`, `end`).
- `condition: "on_success"` (string). Must be `condition: { "type": "on_success" }`.
- Conditional node with only 1 outgoing edge (or 3+). Exactly 2, both required, with `if_true` / `if_false` (or similar bipartite split).
- Forgetting `objects: []` or `inputs: []` when there are no legacy objects or workflow inputs.
- Setting `simulation_validated: true` after editing.
- Authoring `simulation_result` / `last_simulation_timestamp` — the engine writes these.
- Referencing skills that don't exist in the project yet. Scaffold them first or repoint the node.

## After writing

- Re-run `scripts/validate_project.py` and show the output.
- Ask the user: "Want to set this as `active_workflow` in project.json?"
- If yes, edit project.json with T2 ceremony.
- Ask: "Want a custom canvas for this workflow?" — if yes, route to `authoring-canvas.md`.
