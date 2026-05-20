# Flow: develop mode

You're in a folder that already has `project.json` plus standard subfolders. Help the user develop the project: add new items, modify existing ones, or refactor cross-file references.

## Entry checklist

1. Run `scripts/validate_project.py` first. Output is JSON. Show the user any errors/warnings up front so you both have shared ground truth about the current state.
2. **If the validator already reports errors**, capture the error count as a *baseline*. After any change you make, re-run the validator and verify the error count did **not increase**. The user may have a known-broken project they're slowly fixing; your changes must not make it worse.
3. List the project's contents at a high level (counts from the validator's `summary` are enough).
4. Ask the user what they want to do. One question, multiple-choice form preferred:

```
What would you like to do in this project?
  (a) Add a new <item> (skill / workflow / world / object / canvas)
  (b) Modify an existing <item>
  (c) Refactor (rename, version bump, cross-file change)
  (d) Fix a consistency issue from the validator output
  (e) Something else (describe)
```

## Routing

- **(a) Add**: route to the matching `authoring-*.md` flow:
  - skill → `authoring-skill.md`
  - workflow → `authoring-workflow.md`
  - world → `authoring-world.md`
  - object → `authoring-object.md`
  - canvas → `authoring-canvas.md`
- **(b) Modify existing**: go to "Modify" below.
- **(c) Refactor**: route to `refactor-flow.md`.
- **(d) Fix consistency issue**: go to "Fix" below.

## Modify (T2 — diff + confirmation required)

For any change to an existing file:

1. **Read the current file** in full. Quote what's there.
2. **Ask clarifying questions** about the change (one at a time).
3. **Compute the proposed change** as a diff against the current file.
4. **Show the user the diff** (use a unified diff format, with file path).
5. **Wait for explicit confirmation** — phrases like "yes", "go ahead", "apply", or "ship it". Pause indefinitely; never proceed on silence.
6. **Apply via Edit** — not Write — to keep the change localized and review-able. Bump `updated_at` if the file carries one.
7. **Re-run `validate_project.py`** to confirm nothing else broke.
8. Show the user the validator output, then ask "anything else?".

Examples of modify operations:
- Change a workflow's `name` or `description`.
- Add or remove a parameter from a skill's `metadata.yaml`.
- Add a node or edge to a workflow (also see "Add to existing workflow" in `authoring-workflow.md`).
- Update a world's `objects[]` to add or remove an instance.
- Update an object's `anchors` map.

## Fix (T2 — diff + confirmation)

When the validator reports an error, surface it to the user with options:

```
The validator reports: project.json's active_workflow "pick_v1" points to a workflow that doesn't exist.

Options:
  (1) Point active_workflow at an existing workflow [list of workflow_ids found]
  (2) Scaffold workflows/pick_v1.json so the reference resolves
  (3) Set active_workflow to "" (no default workflow)
  (4) Something else

Which?
```

Other common consistency errors and remedies:

| Error | Options |
|---|---|
| `active_world` references missing world | (1) point at existing world, (2) scaffold the missing world, (3) clear field |
| Workflow's `node.skill_id` references missing skill | (1) scaffold the missing skill, (2) repoint the node at an existing skill, (3) remove the node and its edges |
| Workflow's `canvas_ui.source_ref` references missing TSX | (1) scaffold the canvas, (2) clear `canvas_ui` (fall back to auto-generated form) |
| Conditional node has != 2 outgoing edges | Ask user; they likely want to add or remove an edge |
| Off-spec edge_id (`e0`, `e1`, etc.) | (1) rename to `edge_<index>` (also updates references — none in practice since edges aren't referenced) |
| Duplicate node_id or edge_id | Ask user which to keep / how to disambiguate |

Apply the chosen fix with T2 ceremony (diff + confirmation).

## When the user describes a task in natural language

Interpret it, repeat back what you understood, ask the user to confirm, then route. Don't dive in without alignment.

Examples:
- "Make a skill that swirls the plate" → route to `authoring-skill.md` after collecting: name, parameters, scope (does it use existing execution functions or new ones?).
- "Rename my workflow to X" → route to `refactor-flow.md`.
- "The active workflow doesn't exist" → route to Fix above.
- "Add a new world for the lab" → route to `authoring-world.md`.

## After every change

- Re-run `validate_project.py` and surface the result.
- Don't claim "done" — show the validator output and let the user confirm.
- Mention any warnings that aren't blockers but worth knowing.

## Don't

- Don't commit changes (per user CLAUDE.md). Suggest commit messages instead at the end of the session.
- Don't make multiple changes in one diff. One operation per Edit/Write; multiple back-to-back operations confirmed individually.
- Don't auto-bump `version` fields without asking. Version bumps are explicit user intent (route via `refactor-flow.md`).
