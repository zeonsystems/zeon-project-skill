# Example: linear workflow (start → skill → end)

The simplest non-trivial workflow shape. One input passed from the workflow level into a skill node, one skill, one end.

## `workflows/wave_hello.json`

```json
{
  "workflow_id": "wave_hello",
  "name": "Wave Hello",
  "description": "Wave to a selected target object.",
  "version": "1.0.0",
  "author": "user",
  "created_at": "2026-05-19T12:00:00.000Z",
  "updated_at": "2026-05-19T12:00:00.000Z",
  "simulation_validated": false,
  "simulation_result": null,
  "last_simulation_timestamp": null,
  "objects": [],
  "inputs": [
    {
      "name": "target",
      "type": "object",
      "description": "Who to wave at.",
      "is_array": false
    }
  ],
  "nodes": [
    { "node_id": "start_wave_hello_0", "type": "start", "label": "Start" },
    {
      "node_id": "wave_wave_hello_1",
      "type": "skill",
      "label": "Wave",
      "skill_id": "wave",
      "parameters": {
        "target": { "$input": "target" }
      }
    },
    { "node_id": "end_wave_hello_2", "type": "end", "label": "End" }
  ],
  "edges": [
    {
      "edge_id": "edge_0",
      "from_node": "start_wave_hello_0",
      "to_node": "wave_wave_hello_1",
      "condition": { "type": "default" }
    },
    {
      "edge_id": "edge_1",
      "from_node": "wave_wave_hello_1",
      "to_node": "end_wave_hello_2",
      "condition": { "type": "on_success" }
    }
  ]
}
```

## Things to note

- `workflow_id` matches the filename stem.
- `type` field on nodes (not `node_type`).
- Edge IDs `edge_0`, `edge_1` (regex `^edge_\d+$`).
- Start node's outgoing edge has `condition.type = "default"`; skill node's outgoing edge has `"on_success"`.
- Node IDs use the long convention `<type-or-skill_id>_<workflow_id>_<index>`.
- `inputs[].name = "target"` matches the `{"$input": "target"}` reference in the skill node's parameters.
- `simulation_validated` resets to `false` because the workflow changed.

## Cross-references the skill must verify

- `skills/wave/` exists in the project.
- `skills/wave/robotic_code.py` defines `def wave(target)` (or `def wave(target, ...)` with `target` required).
- The `wave` function expects a `SkillObject` (or compatible) for `target`.
