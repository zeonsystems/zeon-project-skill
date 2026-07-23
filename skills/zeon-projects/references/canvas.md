# Canvas — canvas/<workflow_id>_screen.tsx

A canvas is an optional custom React UI that replaces the auto-generated input form when a workflow is run. Most workflows don't need one — the auto-form covers declared inputs. Build a canvas when the user wants richer input UX (plate-map pickers, computed values, guided setup).

## The contract

- One file: `canvas/<workflow_id>_screen.tsx`, `export default` a React component.
- **Only `react` and `react-dom` may be imported** (both are vendored into the iframe; any other import throws at module-evaluation time). The canvas compiles in the browser and runs in a sandboxed, network-less iframe — no other packages, no `fetch`, no external assets. Inline styles work; keep everything self-contained.
- The host injects a `zeon` global (declare it, don't import it):

```tsx
import React, { useState } from "react";

declare const zeon: {
  schema: { name: string; type: string; description?: string; defaultValue?: unknown }[];
  worldObjects: { uuid: string; name: string; displayName?: string }[];
  defaults: Record<string, unknown>;
  submit: (values: Record<string, unknown>) => void;
  onValidationErrors: (cb: (errs: { path: string; message: string }[]) => void) => void;
};

export default function MyFlowScreen() {
  const [values, setValues] = useState<Record<string, unknown>>(() => ({ ...zeon.defaults }));
  const [errors, setErrors] = useState<{ path: string; message: string }[]>([]);
  zeon.onValidationErrors(setErrors);

  return (
    <div style={{ fontFamily: "monospace", padding: 16 }}>
      {/* build inputs from zeon.schema; object pickers from zeon.worldObjects */}
      <button onClick={() => zeon.submit(values)}>Run</button>
    </div>
  );
}
```

- `zeon.schema` mirrors the workflow's declared `inputs` (camelCase field names: `defaultValue`, `isArray`, `itemSchema`). Key the submitted `values` by input **name**; object-typed values should be world object **names** (from `zeon.worldObjects[].name`) — UUIDs also validate and resolve at run time, but prefer names.
- **`zeon.submit(values)` does not run the workflow.** It stages the values with the host and arms the editor's Run button — the operator still presses Run. Label your button "Confirm setup", never "Run". Validation failures come back through `onValidationErrors`.
- The full host global has 11 members. Beyond the five declared above: `setConfirmed(bool)` (gate the Run button — call `setConfirmed(false)` whenever the operator edits a field after confirming, or the editor happily runs stale inputs; re-confirm to re-arm), `setDirty(bool)`, `resetInputs()`, and the live tip-box state trio `tipBoxes`, `onTipCounts(cb)`, `resetTipBox(id)`. Extend the `declare const zeon` block with the members you use.
- The submit-then-edit stale-inputs bug is the most common canvas defect — a canvas that only calls `submit()` leaves Run armed with old values. Track a snapshot of the confirmed values and call `setConfirmed(false)` on any change.

## Wiring it into the workflow

The TSX file does nothing until the workflow references it (see `references/workflows.md`):

```json
"canvas_ui": {
  "kind": "react",
  "source_ref": "canvas/<workflow_id>_screen.tsx",
  "enabled": true,
  "version": 1,
  "updated_at": "<ISO timestamp>"
}
```

`zeon new canvas <workflow_id>` scaffolds the TSX **and** patches the workflow's `canvas_ui` block for you (it aborts if the workflow is missing, already has a `canvas_ui` block, or the TSX exists — so don't pre-add the block). Write `canvas_ui` by hand only when you create the TSX yourself without the CLI. Bump `version` when changing an existing canvas. `source_ref` must match `^canvas/[a-z0-9_]+\.tsx$` (max source size 256 KiB).

## Deriving the form

Read the workflow JSON's `inputs` to decide what to render: `string` → text field, `int`/`float` → number field (respect `defaultValue`), `object` → a select over `zeon.worldObjects` (filter by name prefix if the input description implies a type), `is_array` → repeatable rows, `structured` → fields from `itemSchema`.
