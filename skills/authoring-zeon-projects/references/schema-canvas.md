# Canvas schema

A canvas is an **optional** custom input form for a workflow. It's a single React/TSX file at `canvas/<canvas_id>.tsx`, referenced from a workflow's `canvas_ui` field. If a workflow has no canvas (or `canvas_ui.enabled: false`), the platform renders a standard auto-generated form from the workflow's `inputs`.

A workflow can have **at most one** canvas. A canvas file may exist without a corresponding workflow (orphan), but the skill should flag this.

## File location and naming

Path: `canvas/<canvas_id>.tsx`
- `<canvas_id>` pattern: `^[a-z0-9_]+$` (lowercase, alphanumeric, underscores; no dashes).
- Convention: `<workflow_id>_screen.tsx` (e.g. `pick_place_screen.tsx`), but any name matching the regex works.
- The `source_ref` in the workflow's `canvas_ui` must be `canvas/<canvas_id>.tsx` exactly.

## Wiring from the workflow

The workflow's `canvas_ui` field (see `schema-workflow.md`):

```json
"canvas_ui": {
  "kind": "react",
  "source_ref": "canvas/<canvas_id>.tsx",
  "enabled": true,
  "version": 1,
  "updated_at": "<ISO-8601>"
}
```

`version` is an integer (≥ 1) that increments on every save — it's used as a cache-bust key. The skill MUST bump `version` whenever it rewrites the canvas TSX.

## Runtime sandbox

The TSX is compiled in the browser and executed inside a locked-down sandboxed iframe (no network, no DOM access outside its own root). Only `react` may be imported.

The host injects a `zeon` global:

```ts
declare const zeon: {
  schema: { name: string; type: string; description?: string; defaultValue?: unknown }[];
  worldObjects: { uuid: string; name: string; displayName?: string }[];
  defaults: Record<string, unknown>;
  submit: (values: Record<string, unknown>) => void;
  onValidationErrors: (cb: (errs: { path: string; message: string }[]) => void) => void;
};
```

| Field | Meaning |
|---|---|
| `zeon.schema` | The workflow's `inputs[]` array. The canvas should render one form widget per entry. |
| `zeon.worldObjects` | Selectable objects from the current world, for inputs of `type: "object"`. |
| `zeon.defaults` | Default values for each input (from `defaultValue` in the workflow's `inputs`). |
| `zeon.submit(values)` | Send the collected values to start workflow execution. `values` is keyed by input `name`. |
| `zeon.onValidationErrors(cb)` | Register a handler called when `submit` is rejected — `errs[].path` is the input name, `.message` is the reason. |

## Required exports

The TSX file MUST `export default` a React component. No named exports are honoured. No props are passed in.

## Minimum valid canvas (boilerplate the skill can emit)

```tsx
import React, { useState } from "react";

declare const zeon: {
  schema: { name: string; type: string; description?: string; defaultValue?: unknown }[];
  worldObjects: { uuid: string; name: string; displayName?: string }[];
  defaults: Record<string, unknown>;
  submit: (values: Record<string, unknown>) => void;
  onValidationErrors: (cb: (errs: { path: string; message: string }[]) => void) => void;
};

export default function WorkflowScreen() {
  const [values, setValues] = useState<Record<string, unknown>>(() => ({ ...zeon.defaults }));
  const [errors, setErrors] = useState<{ path: string; message: string }[]>([]);

  zeon.onValidationErrors(setErrors);

  const set = (name: string, val: unknown) =>
    setValues((v) => ({ ...v, [name]: val }));

  return (
    <div style={{ fontFamily: "monospace", padding: 16, maxWidth: 480 }}>
      {zeon.schema.map((input) => {
        const val = values[input.name];
        return (
          <div key={input.name} style={{ marginBottom: 8, display: "flex", gap: 8 }}>
            <label style={{ width: 160, fontSize: 12 }} title={input.description}>
              {input.name}
            </label>
            {input.type === "object" ? (
              <select
                value={String(val ?? "")}
                onChange={(e) => set(input.name, e.target.value)}
              >
                <option value="">— select —</option>
                {zeon.worldObjects.map((o) => (
                  <option key={o.uuid} value={o.name}>
                    {o.displayName || o.name}
                  </option>
                ))}
              </select>
            ) : input.type === "string" ? (
              <input
                type="text"
                value={String(val ?? "")}
                onChange={(e) => set(input.name, e.target.value)}
              />
            ) : (
              <input
                type="number"
                step="any"
                value={val === undefined || val === "" ? "" : Number(val)}
                onChange={(e) =>
                  set(input.name, e.target.value === "" ? "" : Number(e.target.value))
                }
              />
            )}
          </div>
        );
      })}

      {errors.length > 0 && (
        <div style={{ color: "red", fontSize: 12, marginTop: 8 }}>
          {errors.map((e, i) => (
            <div key={i}>⚠ {e.path}: {e.message}</div>
          ))}
        </div>
      )}

      <button
        onClick={() => zeon.submit(values)}
        style={{ marginTop: 14, width: "100%", padding: 8 }}
      >
        Submit
      </button>
    </div>
  );
}
```

Adapted from `golden-gate-assembly-mp6n1k2x/canvas/golden_gate_assembly_v2_screen.tsx`.

## Generating a canvas from a workflow's inputs

When the user asks for a canvas alongside a workflow, the skill should:

1. Read the workflow's `inputs[]`.
2. Emit one form widget per input, based on `input.type`:
   - `string` → text input.
   - `int` → number input (with `step="1"`).
   - `float` → number input (with `step="any"`).
   - `object` → `<select>` over `zeon.worldObjects` when non-empty, fallback to text input.
   - `structured` → fall back to JSON textarea **and** flag to the user that a richer renderer would help.
   - Any input with `is_array: true` → list editor (add / remove rows); the boilerplate above does NOT handle arrays — extend per-case.
3. Initialize state from `zeon.defaults`.
4. Wire `submit` and `onValidationErrors`.
5. Set the workflow's `canvas_ui.version` to `1` for a new canvas, or bump if updating an existing one.
6. Match `source_ref` to the actual file path.

## Validation the skill should run

1. The file ends in `.tsx`.
2. The file contains an `export default function` or `export default class` (React component).
3. The file does NOT import anything other than `react` (sandbox restriction).
4. The file does NOT use `fetch`, `XMLHttpRequest`, `window`, or `document` APIs that the sandbox blocks. (Simple grep is enough; deep analysis is overkill.)
5. The workflow's `canvas_ui.source_ref` matches the file path.
6. The workflow's `canvas_ui.version` is an integer ≥ 1, bumped if the file changed.

## Common mistakes

- Importing libraries other than `react` (lodash, axios, etc.). They won't load.
- Forgetting `export default`. The host can't mount the component.
- Hardcoding input names into the JSX instead of mapping `zeon.schema`. Breaks when the workflow's `inputs` change.
- Calling `zeon.submit` with values that don't match `inputs[].name` keys. The submission will be rejected with a validation error.
- Not bumping `canvas_ui.version` after edit — the browser may serve a stale cached build.
- Putting business logic / robotics calls in the canvas. The canvas only collects input values; the workflow runs the skills.
