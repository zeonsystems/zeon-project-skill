# Flow: author a canvas

A canvas is an optional custom input form for one workflow. It's a TSX file at `canvas/<workflow_id>_screen.tsx`, referenced from the workflow's `canvas_ui` field. A workflow has at most one canvas; without one, the platform renders a standard auto-generated form.

**Schemas**: `references/schema-canvas.md`, `references/schema-workflow.md`. Example: `examples/canvas-from-workflow-inputs.md`.

## Required information (interview)

Ask one at a time:

1. **Which workflow does this canvas belong to?** Must be an existing workflow (`workflows/<id>.json`). The canvas's filename and component name are derived from the workflow id.
2. **What inputs does the workflow have?** Run `scripts/extract_workflow_inputs.py workflows/<workflow_id>.json` and review with the user.
3. **Custom widgets needed?** If the user wants something beyond the default (text / number / select), ask what.

## Generation

1. Run `scripts/invoke_scaffold.py item canvas <workflow_id>`. The script emits a single file at `canvas/<workflow_id>_screen.tsx` containing a minimal React stub:
   - Default-exports a component named `<PascalCase(workflow_id)>Screen`.
   - Wires `zeon.onValidationErrors` to local state.
   - Has a `TODO` comment in the body and a single `Submit` button calling `zeon.submit(values)`.
2. Write the file via `Write`.
3. Replace the TODO body with the actual form. For each entry in `zeon.schema`, render a widget matching `input.type` (see the type→widget table in `references/schema-canvas.md`).
4. If the user wants the rich-form pattern, the elaborate example in `examples/canvas-from-workflow-inputs.md` walks through one input per row with type-switched widgets.

## Wiring the canvas into the workflow (T2)

After writing the TSX:

1. Read `workflows/<workflow_id>.json`.
2. Build the new `canvas_ui` block:
   ```json
   "canvas_ui": {
     "kind": "react",
     "source_ref": "canvas/<workflow_id>_screen.tsx",
     "enabled": true,
     "version": 1,
     "updated_at": "<ISO-8601 now>"
   }
   ```
3. Show the user the unified diff for the workflow.
4. Wait for confirmation.
5. Apply via `Edit`. Bump the workflow's `updated_at`.

## Modifying an existing canvas (T2)

If the user edits an existing canvas:

1. Read the current TSX.
2. Compute the new content.
3. Show diff. Wait for confirmation.
4. Write the new TSX.
5. Bump the workflow's `canvas_ui.version` (next integer) and `canvas_ui.updated_at` — applies a T2 modification on the workflow file with diff.

## Validation

1. The TSX has `export default` for a function or class.
2. The only `import ... from "..."` line points to `"react"`.
3. The file is under 256 KB (the runtime cap).
4. No use of `fetch`, `XMLHttpRequest`, `window.location`, etc. (sandbox blocks them).
5. `scripts/validate_project.py` confirms `canvas_ui.source_ref` resolves to a file on disk and the workflow's `canvas_ui` shape is correct.

## Cross-reference checks

- Workflow's `canvas_ui.source_ref` matches the canvas file path exactly (`canvas/<workflow_id>_screen.tsx`).
- The canvas widget switching on `input.type` covers every type that appears in the workflow's `inputs[]`.
- The canvas does not depend on input names that don't appear in `inputs[]` — the canvas should iterate `zeon.schema` rather than hardcode keys.

## Common mistakes

- Importing non-react libraries. The sandbox blocks them.
- Forgetting `export default`. The host can't mount the component.
- Hardcoding `inputs[i].name` strings instead of mapping `zeon.schema`. Breaks when inputs change.
- Calling `zeon.submit({})` with values that don't match `inputs[].name`. The submission is rejected.
- Not bumping `canvas_ui.version` after a TSX edit. Browser may serve stale build.
- Writing the TSX without also wiring the workflow's `canvas_ui` field — orphan canvas. The skill should always do both steps in the same session.
- Naming the file `canvas/<id>.tsx` instead of `canvas/<workflow_id>_screen.tsx`. The `_screen` suffix is the convention; `primary_path_for` and the scaffolder both assume it.

## After writing

- Re-run `scripts/validate_project.py`.
- Suggest: "Open the workflow in the Zeon product to verify the canvas renders correctly. The first time, the form should match what we just authored."
