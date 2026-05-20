# Example: workflow with a conditional branch

A workflow that runs a check, then either proceeds with the main path or routes to a fallback skill. Demonstrates `conditional` nodes and `if_true` / `if_false` edges.

## `workflows/check_and_pick.json`

```json
{
  "workflow_id": "check_and_pick",
  "name": "Check and Pick",
  "description": "Verify the target is reachable, then pick it; otherwise log a warning.",
  "version": "1.0.0",
  "author": "user",
  "created_at": "2026-05-19T12:00:00.000Z",
  "updated_at": "2026-05-19T12:00:00.000Z",
  "simulation_validated": false,
  "simulation_result": null,
  "last_simulation_timestamp": null,
  "objects": [],
  "inputs": [
    { "name": "target", "type": "object", "description": "Object to pick.", "is_array": false }
  ],
  "nodes": [
    { "node_id": "start_check_and_pick_0", "type": "start", "label": "Start" },
    {
      "node_id": "check_reach_check_and_pick_1",
      "type": "skill",
      "label": "Check reachability",
      "skill_id": "check_reachable",
      "parameters": {
        "target": { "$input": "target" }
      }
    },
    {
      "node_id": "branch_check_and_pick_2",
      "type": "conditional",
      "label": "Reachable?",
      "condition": {
        "expression": "target_reachable == true",
        "description": "Set true by check_reachable's postcondition."
      }
    },
    {
      "node_id": "pick_check_and_pick_3",
      "type": "skill",
      "label": "Pick",
      "skill_id": "grab_object",
      "parameters": {
        "object": { "$input": "target" }
      }
    },
    {
      "node_id": "warn_check_and_pick_4",
      "type": "skill",
      "label": "Log warning",
      "skill_id": "log_warning",
      "parameters": {
        "message": "Target not reachable"
      }
    },
    { "node_id": "end_check_and_pick_5", "type": "end", "label": "End" }
  ],
  "edges": [
    { "edge_id": "edge_0", "from_node": "start_check_and_pick_0",       "to_node": "check_reach_check_and_pick_1", "condition": { "type": "default" } },
    { "edge_id": "edge_1", "from_node": "check_reach_check_and_pick_1", "to_node": "branch_check_and_pick_2",       "condition": { "type": "on_success" } },
    { "edge_id": "edge_2", "from_node": "branch_check_and_pick_2",       "to_node": "pick_check_and_pick_3",         "condition": { "type": "if_true" } },
    { "edge_id": "edge_3", "from_node": "branch_check_and_pick_2",       "to_node": "warn_check_and_pick_4",         "condition": { "type": "if_false" } },
    { "edge_id": "edge_4", "from_node": "pick_check_and_pick_3",          "to_node": "end_check_and_pick_5",           "condition": { "type": "on_success" } },
    { "edge_id": "edge_5", "from_node": "warn_check_and_pick_4",          "to_node": "end_check_and_pick_5",           "condition": { "type": "on_success" } }
  ]
}
```

## Validation rules at play

- The `conditional` node `branch_check_and_pick_2` has **exactly 2 outgoing edges** with `if_true` and `if_false` condition types — required.
- Both branches converge on the same `end` node — fine, that's not a cycle.
- The expression `target_reachable == true` references a state variable that `check_reachable`'s postcondition is expected to set. The runtime does not statically check this; if the skill doesn't actually set `target_reachable`, the branch will always evaluate to `false`.

## What the skill must verify when generating this

- All four skill_ids (`check_reachable`, `grab_object`, `log_warning`) exist in the project.
- The expression on the conditional node is a runtime-evaluable boolean — verify the state variable is plausible.
- The `condition.expression` field is present (required for `conditional` node type).
