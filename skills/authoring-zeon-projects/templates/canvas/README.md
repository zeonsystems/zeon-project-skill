# canvas/

Optional **canvases** for this project's workflows.

A canvas is a single React/TSX file, `canvas/<canvas_id>.tsx`, that collects a
workflow's inputs with a bespoke UI instead of the standard auto-generated
form. A workflow opts in via its `canvas_ui` field:

```json
"canvas_ui": {
  "kind": "react",
  "source_ref": "canvas/<canvas_id>.tsx",
  "enabled": true,
  "version": 1,
  "updated_at": "<ISO 8601>"
}
```

The canvas is compiled in the browser and rendered inside a locked-down
sandboxed iframe. It has **no network access**. The host injects these
globals:

- `zeon.schema` — the workflow's `WorkflowInput[]`
- `zeon.worldObjects` — `[{ uuid, name, displayName }]`
- `zeon.defaults` — declared default values
- `zeon.submit(values)` — hand the collected values to the graph
- `zeon.onValidationErrors(cb)` — called if a submit is rejected

The file must `export default` a React component. Only `react` may be
imported. Submitted values must conform to the workflow's declared `inputs`
schema (keyed by input name); they are validated before the workflow runs.
Remove or set `enabled: false` to fall back to the standard form.
