# Example: linear workflow (single skill)

This is the real `test_platefuge.json` workflow from the `golden-gate-assembly` project. Minimal shape: start → one skill → end, with three `inputs` (two objects + one number) and parameter-binding via `{"$input": ...}`.

Source: `golden-gate-assembly-mp6n1k2x/workflows/test_platefuge.json`.

## `workflows/test_platefuge.json`

```json
{
  "workflow_id": "test_platefuge",
  "name": "Test Platefuge",
  "description": "Minimal test: pick reaction plate → load rotor → spin → unload → place.",
  "version": "1.0.0",
  "author": "bkolar",
  "created_at": "2026-05-16T00:00:00.000Z",
  "updated_at": "2026-05-16T00:00:00.000Z",
  "simulation_validated": false,
  "objects": [],
  "inputs": [
    { "name": "reaction_plate",  "type": "object", "is_array": false, "description": "Wellplate to spin" },
    { "name": "wellplate_stand", "type": "object", "is_array": false, "description": "Stand to return plate to after spin" },
    { "name": "spin_duration",   "type": "float",  "description": "Spin time in seconds", "defaultValue": 10 }
  ],
  "nodes": [
    { "node_id": "start_0", "type": "start", "label": "Start" },
    {
      "node_id": "platefuge_1",
      "type": "skill",
      "label": "Run Platefuge",
      "skill_id": "run_platefuge",
      "parameters": {
        "object":          { "$input": "reaction_plate" },
        "wellplate_stand": { "$input": "wellplate_stand" },
        "slot_index":      1,
        "spin_duration":   { "$input": "spin_duration" }
      }
    },
    { "node_id": "end_2", "type": "end", "label": "End" }
  ],
  "edges": [
    { "edge_id": "e0", "from_node": "start_0",     "to_node": "platefuge_1", "condition": { "type": "default" } },
    { "edge_id": "e1", "from_node": "platefuge_1", "to_node": "end_2",       "condition": { "type": "on_success" } }
  ]
}
```

## Patterns to learn from

- **`workflow_id` matches the filename stem** — both `test_platefuge`.
- **`type` field** on nodes (not `node_type`).
- **Edge IDs `e0`, `e1`** (regex `^e\d+$`).
- **Node IDs** here use a `<role>_<index>` form (`start_0`, `platefuge_1`, `end_2`) — also valid. The scaffold's own default workflow uses bare role names (`start`, `grab`, `end`). Either form works as long as the regex `^[a-z0-9_]+$` holds.
- **`condition.type = "default"`** on the start edge; `"on_success"` for the normal continue.
- **`objects: []` and `inputs: [...]` both present** — `objects` may be empty but the field must exist.
- **Three input types shown**: two `object` inputs (resolved by the user/canvas to specific world-object UUIDs) and one `float` with `defaultValue: 10`.
- **Parameter binding**: three keys use `{"$input": "name"}` to draw from the workflow's inputs; one (`slot_index`) is a JSON literal `1`.
- **`description` field at node level** would also be allowed (this example omits it on the skill node).

## Cross-references the skill must verify

- `skills/run_platefuge/` exists in the project.
- `skills/run_platefuge/robotic_code.py` defines `def run_platefuge(object, wellplate_stand, slot_index=..., spin_duration=...)` — parameter names must match.
- The workflow's `inputs[].name` values (`reaction_plate`, `wellplate_stand`, `spin_duration`) are referenced from `parameters` via `{"$input": "..."}`.
