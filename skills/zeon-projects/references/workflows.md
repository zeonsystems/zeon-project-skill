# Workflows — workflows/<workflow_id>.json

> Hosted docs: [Authoring a workflow](https://readme.zeonsystems.app/docs/authoring-a-workflow.md) · [The workflow file](https://readme.zeonsystems.app/docs/workflows-json.md)

A workflow is a directed graph of skills, one strict-JSON file per workflow. It binds *roles*, not hardware: inputs are declared abstractly and mapped to world objects at run time, which is what lets one graph run on different benches.

## Required shape

```json
{
  "workflow_id": "my_flow",
  "name": "My flow",
  "description": "",
  "version": "1.0.0",
  "author": "",
  "created_at": "2026-06-20T00:00:00.000Z",
  "updated_at": "2026-06-20T00:00:00.000Z",
  "simulation_validated": false,
  "objects": [],
  "inputs": [],
  "nodes": [
    { "node_id": "start", "type": "start", "label": "Start" },
    { "node_id": "end", "type": "end", "label": "End" }
  ],
  "edges": [
    { "edge_id": "e0", "from_node": "start", "to_node": "end",
      "condition": { "type": "default" } }
  ]
}
```

`"objects": []` is required even when empty (legacy alias mechanism — leave `[]` unless maintaining an old project). Strict JSON: no comments, no trailing commas. Set `simulation_validated` back to `false` whenever you change the graph. The filename stem must equal `workflow_id` — the platform always persists to `<workflow_id>.json`, so a mismatch leaves a stale duplicate after any editor round-trip.

**Saving is not validating.** The gateway saves a workflow even when its validation fails (errors ride back in the response, the file persists), rewrites `updated_at`, and strips null-valued fields on every save. Run `scripts/validate.py` — a 200 from the editor proves nothing about runnability.

## Validation rules the platform enforces on save

- `workflow_id` present, `^[a-z0-9_]+$`, and should equal the filename stem.
- `name` present; `version` present and semver (`1.0.0`).
- ≥ 2 nodes; at least one `start` and one `end` node; ≥ 1 edge.
- Every edge's `from_node`/`to_node` names an existing `node_id`.

## Nodes

`type` is one of `start` | `end` | `skill` | `loop` | `conditional`. Every node needs `node_id` and `label`; `description` is optional.

Skill nodes need `skill_id` (must exist under `skills/`) and `parameters` — always present, `{}` when the skill takes none:

```json
{
  "node_id": "aspirate",
  "type": "skill",
  "label": "Aspirate",
  "skill_id": "epipette_grey_aspirate",
  "parameters": {
    "object": { "$input": "plate" },
    "anchor": { "$input": "well" },
    "volume": { "$input": "volume" }
  }
}
```

Parameter **keys must match the skill function's parameter names** (here `epipette_grey_aspirate(object, anchor, volume, …)` — the input can be named anything, e.g. `well`). Values are either a literal or a `{"$input": "<input name>"}` reference. At run time a missing required parameter **aborts the node**, and an unknown key is **silently dropped** (a typo'd optional parameter runs with the default, no error) — `scripts/validate.py` cross-checks node parameters against the actual signature.

Other node fields: `loop` (loop nodes: `{type: count|collection|conditional, iterations|source|expression}`), `condition` (conditional nodes: `{expression, description}`). **Do not use `retry` on skill nodes — the executor never reads it** (a runtime no-op that only looks like error handling); build retries inside the skill instead (`references/patterns.md`). Loop and conditional nodes run in the executor but can't be created or edited in the visual editor today — if you use them, tell the user the graph won't be fully editable visually.

The executor's semantics for all of this — exception-driven failure routing, the tiny conditional-expression grammar, collection-loop `source` resolution, `current_item` injection — are in `references/execution-model.md`. Read it before authoring conditionals, loops, or failure paths.

## Edges

```json
{ "edge_id": "e1", "from_node": "pick", "to_node": "aspirate",
  "condition": { "type": "on_success" } }
```

- `condition.type`: `default` (unconditional, used from `start`), `on_success`, `on_failure`, and the branch variants `if_true` / `if_false` (conditional nodes), `loop_continue` / `loop_complete` (loop nodes).
- **A `default` edge out of a skill node fires even when the skill fails** — use `on_success` between sequential skill nodes (`references/execution-model.md`).
- Conditional and loop nodes need exactly two outgoing edges (their two branches).
- Edge ids must be unique; the platform convention is `e0`, `e1`, … Node ids must be identifier-safe (`fill_loop`, not `fill-loop`) — loop ids are embedded in executor expressions.

## Inputs

```json
"inputs": [
  { "name": "plate",  "type": "object", "is_array": false, "description": "PCR wellplate" },
  { "name": "well",   "type": "string", "description": "Well (A1–H12)", "defaultValue": "A1" },
  { "name": "volume", "type": "float",  "description": "Volume in µL", "defaultValue": 5 }
]
```

- `type`: `string` | `int` | `float` | `object` | `structured`. `object` = a world object reference; `structured` = schema-based data with `itemSchema`.
- `is_array` / `isArray` for multi-value inputs (both spellings accepted; array-of-structured uses `itemSchema` to type each item).
- **Object input values should be world object *names*** (the `metadata.name` of an instance in the world, e.g. `wellplate_pcr_parts_1`). Prefer names — they stay stable across world rebuilds; UUIDs are accepted and resolved at run time but are brittle.
- Names match `^[A-Za-z][A-Za-z0-9_]*$`.
- **Never put UUID-shaped strings through `string` inputs or defaults** (barcodes, filenames): at run time any string containing a UUID is auto-treated as a world object reference, and the lookup miss aborts the skill.

## canvas_ui (optional)

Attach a custom run UI (see `references/canvas.md`):

```json
"canvas_ui": {
  "kind": "react",
  "source_ref": "canvas/my_flow_screen.tsx",
  "enabled": true,
  "version": 1,
  "updated_at": "2026-06-20T00:00:00.000Z"
}
```

`source_ref` must match `^canvas/[a-z0-9_]+\.tsx$` and point at an existing file. Omit the block (or `"enabled": false`) to use the auto-generated input form — which is the sensible default; only build a canvas when the user wants one.
