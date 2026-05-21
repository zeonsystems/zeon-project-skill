# Workflow schema

A workflow is a single JSON file at `workflows/<workflow_id>.json`. The on-disk format is the **Workflow standard** — distinct from the in-memory `ExecutionGraph` used at execution time. The two are converted by `frontend/src/utils/workflow-transform.ts` (TypeScript) and `services/gateway/src/gateway/routers/workflows.py` (Python).

**Write the on-disk Workflow format.** Don't write `ExecutionGraph` shape (`graph_id`, `node_type`, string `condition`) — that's only for execution-time in-memory objects.

Pydantic source-of-truth for the on-disk format: `services/gateway/src/gateway/routers/workflows.py:60-220` (`WorkflowInput`, `WorkflowObject`, `WorkflowCanvasUI`, `Offset`, `ObjectReference`, plus the model classes for the workflow itself).

JSON Schema (descriptive, not enforced at runtime but matches the Pydantic): `docs/structure-templates/workflow/schema.json`.

---

## Top-level fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `workflow_id` | string | yes | Pattern `^[a-z0-9_]+$`. Must match the filename stem. |
| `name` | string | yes | Display name. |
| `description` | string | no | Detailed description. |
| `version` | string | yes | Semantic version `^\d+\.\d+\.\d+$`. |
| `author` | string | yes | Email or username. Empty string `""` is acceptable. |
| `created_at` | ISO-8601 string | yes | Set on creation. |
| `updated_at` | ISO-8601 string | yes | Bump on every save. |
| `simulation_validated` | bool | no | Defaults `false`. Set `false` whenever nodes/edges/params change. |
| `objects` | array | yes (may be `[]`) | Legacy generic object declarations. See below. |
| `inputs` | array | yes (may be `[]`) | Workflow-level inputs. See below. |
| `nodes` | array | yes (≥ 2) | At least 1 start + 1 end. |
| `edges` | array | yes (≥ 1) | Connections between nodes. |
| `canvas_ui` | object | no | Custom React canvas reference. |

`simulation_result` and `last_simulation_timestamp` are runtime fields the engine writes after a sim run completes. Don't author them — leave them out of fresh files; the engine adds them when it has something to put there.

## `nodes[]`

Each node:

```json
{
  "node_id": "<pattern: ^[a-z0-9_]+$>",
  "type": "start | end | skill | loop | conditional",
  "label": "Short display name",
  "description": "(optional) Longer description",
  ...type-specific fields below
}
```

### Node-type-specific fields

#### `start` / `end`
No extra fields. `start` is required exactly once; `end` is required at least once.

#### `skill`
Required: `skill_id`, `parameters`.

```json
{
  "node_id": "pick_object_pick_place_1",
  "type": "skill",
  "label": "Pick Object",
  "skill_id": "pick_object",
  "parameters": {
    "object": { "$input": "target_cup" },
    "force": 25.0
  },
  "retry": 2
}
```

`parameters` keys are the skill's parameter names. Each value is one of:
- **Input reference**: `{"$input": "<input_name>"}` — resolved at execution time from `inputs[]`.
- **World-object reference (by instance id)**: `{"object_ref": "<instance_id>"}` — references a specific instance in the active world's `world_state.json` `objects` map (the key includes the UUID, e.g. `bottle_35582ed6-be64-4e11-81d1-843e9bed5502`). This is the form the bundled `pick_place.json` example uses.
- **Object reference (alias + offset)**: `{"alias": "<obj_alias>", "offset": {"xyz": [x,y,z], "wxyz": [w,x,y,z]}}` — refers to an entry in `objects[]` with optional position/rotation offset.
- **Literal**: any JSON primitive (string, number, bool) or container — passed directly to the skill function.

`retry` is optional and overrides the default retry count for this node.

#### `loop`
Required: `loop`.

```json
{
  "node_id": "loop_my_workflow_3",
  "type": "loop",
  "label": "Repeat 5×",
  "loop": {
    "type": "count",
    "iterations": 5
  }
}
```

`loop.type`: one of `count`, `collection`, `conditional`.
- `count`: requires `iterations` (int ≥ 1).
- `collection`: requires `source` (string — state variable name).
- `conditional`: requires `expression` (string — boolean expression).

Loop nodes must have exactly 2 outgoing edges: one for the loop body and one for loop exit.

#### `conditional`
Required: `condition`.

```json
{
  "node_id": "check_my_workflow_4",
  "type": "conditional",
  "label": "Verify pose",
  "condition": {
    "expression": "pose_ok == true",
    "description": "True when the gripper reached the target pose"
  }
}
```

Conditional nodes must have exactly 2 outgoing edges with `condition.type` values that the executor distinguishes (commonly `if_true` and `if_false`).

### Node ID convention

Short, semantic names per role — `start`, `end`, plus one per skill or branch (`grab`, `move`, `drop`, `branch`, etc.). This matches what `zeon_project_scaffold._scaffold._workflow_files` emits and what the bundled `pick_place.json` example uses.

Example (workflow `pick_place`):
- `start`
- `grab`
- `move`
- `drop`
- `end`

The loader only enforces the regex `^[a-z0-9_]+$`. Disambiguate collisions with a suffix (`grab_a`, `grab_b`). Avoid embedding the workflow id in node ids.

## `edges[]`

```json
{
  "edge_id": "e<index>",
  "from_node": "<existing node_id>",
  "to_node": "<existing node_id>",
  "condition": { "type": "<see below>" }
}
```

| Field | Constraint |
|---|---|
| `edge_id` | Pattern `^e\d+$`. The scaffold emits `e0, e1, ...`. |
| `from_node` | Must exist in `nodes[]`. |
| `to_node` | Must exist in `nodes[]`. |
| `condition.type` | See condition types below. |

### Edge condition types

Used in `condition.type`:

| Value | When to use |
|---|---|
| `default` | Outgoing edge from `start` (and as a no-condition transition elsewhere). |
| `on_success` | Continue if the previous node succeeded. |
| `on_failure` | Branch on failure (typically to a cleanup or end node). |
| `if_true` | One of two outgoing edges of a `conditional` node. |
| `if_false` | The other outgoing edge of a `conditional` node. |
| `loop_continue` | Body of a `loop` node — feeds back into the loop. |
| `loop_complete` | Exit edge of a `loop` node. |

Source for the mapping: `frontend/src/utils/workflow-transform.ts:103-150`.

## `inputs[]`

Workflow-level inputs. Each input is filled in at launch time (via the canvas or auto-generated form) and referenced from `nodes[].parameters` via `{"$input": "<name>"}`.

```json
{
  "name": "target_cup",
  "type": "object",
  "description": "The cup to pick up.",
  "is_array": false,
  "default_value": null
}
```

Fields:
| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | Pattern `^[A-Za-z][A-Za-z0-9_]*$` — letters/numbers/underscores, starts with letter. PascalCase and snake_case both allowed. |
| `type` | enum | yes | One of `string`, `int`, `float`, `object`, `structured`. (No `boolean`/`array` here — use `is_array: true` for arrays.) |
| `is_array` | bool | no, default `false` | Set `true` for an array input. Alias: `isArray` (both accepted at parse). |
| `description` | string | no | Shown in the canvas form. |
| `default_value` | any | no | Default value if absent. Alias: `defaultValue`. |
| `item_schema` | dict | no | Required when `is_array: true` and `type: "structured"`. Recursive `ItemSchemaField` map. |

The Pydantic config uses `populate_by_name = True`, so both `is_array`/`isArray` and `default_value`/`defaultValue` parse correctly. **Prefer snake_case** for new files; the camelCase aliases exist for backward compatibility with files saved by the frontend.

## `objects[]`

Legacy generic-object declarations. Each entry:

```json
{
  "alias": "target_cup",
  "mesh_type": "coffee_cup",
  "display_name": "Target Cup"
}
```

| Field | Constraint |
|---|---|
| `alias` | Pattern `^[a-z0-9_]+$`. Used as the `alias` key in node-parameter ObjectReferences. |
| `mesh_type` | Name of an object type from the mesh database OR a project-local `objects/<mesh_type>/`. |
| `display_name` | Human-readable name shown in the UI. |

Modern workflows often have `objects: []` and pass objects via `inputs` of `type: "object"` instead — but the field is still required (can be empty array).

## `canvas_ui`

Optional. Reference to a `canvas/<id>.tsx` file that renders a custom input form.

```json
{
  "kind": "react",
  "source_ref": "canvas/my_workflow_screen.tsx",
  "enabled": true,
  "version": 1,
  "updated_at": "2026-05-19T12:00:00.000Z"
}
```

| Field | Constraint |
|---|---|
| `kind` | Must be `"react"` (only supported renderer today). |
| `source_ref` | Pattern `^canvas/[a-z0-9_]+\.tsx$`. |
| `enabled` | If `false`, the runtime falls back to the auto-generated form. |
| `version` | Integer ≥ 1, bumped on each canvas save (cache-bust). |
| `updated_at` | ISO-8601 string. Optional. |

See `schema-canvas.md` for the TSX shape the canvas file must export.

## Structural validation rules (`ExecutionGraph.validate_graph_structure`)

The executor will refuse to run a workflow that violates these (`graph_models.py:298-326`):

1. No orphaned nodes (every node referenced by ≥ 1 edge).
2. Exactly one `start` node.
3. At least one `end` node.
4. Every edge's `from_node`/`to_node` exists in `nodes[]`.
5. `conditional` nodes have exactly 2 outgoing edges.
6. `loop` nodes have valid `loop` config and 2 outgoing edges (body + exit).
7. No unintended cycles (excluding `loop_body` and `retry_body` edges which create *intentional* loops).

The skill must run these checks before writing — broken workflows are silent disk errors at author-time and screaming runtime errors later.

## Minimal valid workflow (start → end with one skill)

```json
{
  "workflow_id": "hello",
  "name": "Hello",
  "description": "",
  "version": "1.0.0",
  "author": "",
  "created_at": "2026-05-20T12:00:00.000Z",
  "updated_at": "2026-05-20T12:00:00.000Z",
  "simulation_validated": false,
  "objects": [],
  "inputs": [],
  "nodes": [
    { "node_id": "start", "type": "start", "label": "Start" },
    { "node_id": "wave",  "type": "skill", "label": "Wave",
      "skill_id": "wave", "parameters": {} },
    { "node_id": "end",   "type": "end", "label": "End" }
  ],
  "edges": [
    { "edge_id": "e0", "from_node": "start", "to_node": "wave", "condition": { "type": "default" } },
    { "edge_id": "e1", "from_node": "wave",  "to_node": "end",  "condition": { "type": "on_success" } }
  ]
}
```

## Common mistakes

- Using `node_type` instead of `type` on nodes. **This is `ExecutionGraph` shape, not on-disk.**
- Using `graph_id` instead of `workflow_id`. Same — on-disk uses `workflow_id`.
- `condition: "on_success"` (string). On-disk it must be `condition: { "type": "on_success" }` (object).
- Edge IDs like `edge_0`, `edge_1`. Use `e0`, `e1` — the scaffold's canonical form.
- Long node IDs like `start_<workflow>_0`. Use short semantic names (`start`, `grab`, `end`).
- Forgetting `objects: []` or `inputs: []`. Both fields are required even when empty.
- Skipping `version` or `created_at`. Both are required.
- Setting `simulation_validated: true` after editing nodes/edges. Reset to `false` on any structural change.
- Authoring `simulation_result` / `last_simulation_timestamp` in a fresh file. The engine writes them after a run.
- Mixing input-reference shapes: `{"$input": "name"}` is correct; `{"input": "name"}` and `$name` are wrong.
- Including conditional outgoing edges with `condition.type = "default"`. Conditional nodes need `if_true`/`if_false` (or whatever the user's executor accepts) — not `default`.
