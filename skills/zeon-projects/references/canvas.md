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
- The host global has more members than the five declared above: `setConfirmed(bool)` (gate the Run button — call `setConfirmed(false)` whenever the operator edits a field after confirming, or the editor happily runs stale inputs; re-confirm to re-arm), `setDirty(bool)`, `resetInputs()`, the live tip-box state trio `tipBoxes`, `onTipCounts(cb)`, `resetTipBox(id)`, and `inputPresets` (below). Extend the `declare const zeon` block with the members you use.
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

## Input presets — inputs/*.json → zeon.inputPresets

A project may carry an `inputs/` folder of preset files. Each `*.json` is one
named bundle of workflow-input values:

```json
{
  "_label": "Sample A",
  "plate": "wellplate_pcr_parts_1",
  "well": "B3",
  "volume": 7.5
}
```

- `_label` is the display name (the platform strips it from the values);
  every other key must name a **declared workflow input**, with values in the
  same forms as `zeon.submit` (object inputs = world object names).
- The host exposes them to the canvas as `zeon.inputPresets` —
  `{ id, name, values }[]` (`id` = filename stem, `name` = `_label`) — seeded
  on load and pushed on change like `tipBoxes`. The host never overwrites the
  operator's current selection; applying a preset is the canvas's job.
- The standard preset-canvas shape: dropdown over `zeon.inputPresets` →
  preview the values → operator confirms → `zeon.submit(preset.values)`.
  Presets don't bypass validation — bad values come back through
  `onValidationErrors` as usual.
- **Malformed preset files are silently skipped by the platform** (they just
  vanish from the dropdown) — `scripts/validate.py` errors on unparseable
  preset JSON and warns when a preset key matches no declared input, so run it
  after editing `inputs/`.
- Preset files sync like any other project file (`zeon sync`).

## Deriving the form

Read the workflow JSON's `inputs` to decide what to render: `string` → text field, `int`/`float` → number field (respect `defaultValue`), `object` → a select over `zeon.worldObjects` (filter by name prefix if the input description implies a type), `is_array` → repeatable rows, `structured` → fields from `itemSchema`.
