# Example: canvas for a real workflow

This is the real `golden_gate_assembly_v2_screen.tsx` canvas from the `golden-gate-assembly` project. It renders a custom input form for `golden_gate_assembly_v2.json` (15 inputs — see `examples/workflow-rich.md`).

Sources:
- `golden-gate-assembly-mp6n1k2x/canvas/golden_gate_assembly_v2_screen.tsx`
- `golden-gate-assembly-mp6n1k2x/workflows/golden_gate_assembly_v2.json` (the workflow this canvas attaches to)

## `canvas/golden_gate_assembly_v2_screen.tsx`

```tsx
import React, { useState } from "react";

declare const zeon: {
  schema: { name: string; type: string; description?: string; defaultValue?: unknown }[];
  worldObjects: { uuid: string; name: string; displayName?: string }[];
  defaults: Record<string, unknown>;
  submit: (values: Record<string, unknown>) => void;
  onValidationErrors: (cb: (errs: { path: string; message: string }[]) => void) => void;
};

export default function GoldenGateAssemblyV2Screen() {
  const [values, setValues] = useState<Record<string, unknown>>(() => ({ ...zeon.defaults }));
  const [errors, setErrors] = useState<{ path: string; message: string }[]>([]);

  zeon.onValidationErrors(setErrors);

  const set = (name: string, val: unknown) => setValues((v) => ({ ...v, [name]: val }));

  const s: React.CSSProperties = {
    width: "100%", padding: "5px 7px", fontSize: 13,
    border: "1px solid #ccc", borderRadius: 4, boxSizing: "border-box",
  };

  return (
    <div style={{ fontFamily: "monospace", padding: 16, maxWidth: 480 }}>
      <div style={{ marginBottom: 12, fontWeight: "bold" }}>Golden Gate Assembly v2</div>

      {zeon.schema.map((input) => {
        const val = values[input.name];
        return (
          <div key={input.name} style={{ marginBottom: 8, display: "flex", alignItems: "center", gap: 8 }}>
            <label style={{ width: 160, fontSize: 12, flexShrink: 0 }} title={input.description}>
              {input.name}
            </label>

            {input.type === "object" ? (
              zeon.worldObjects.length > 0 ? (
                <select value={String(val ?? "")} onChange={(e) => set(input.name, e.target.value)} style={s}>
                  <option value="">— select —</option>
                  {zeon.worldObjects.map((o) => (
                    <option key={o.uuid} value={o.name}>{o.displayName || o.name}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  placeholder="object name / id"
                  value={String(val ?? "")}
                  onChange={(e) => set(input.name, e.target.value)}
                  style={s}
                />
              )
            ) : input.type === "string" ? (
              <input
                type="text"
                value={String(val ?? "")}
                onChange={(e) => set(input.name, e.target.value)}
                style={s}
              />
            ) : (
              <input
                type="number"
                step="any"
                value={val === undefined || val === "" ? "" : Number(val)}
                onChange={(e) => set(input.name, e.target.value === "" ? "" : Number(e.target.value))}
                style={s}
              />
            )}
          </div>
        );
      })}

      {errors.length > 0 && (
        <div style={{ marginTop: 8, color: "red", fontSize: 12 }}>
          {errors.map((e, i) => <div key={i}>⚠ {e.path}: {e.message}</div>)}
        </div>
      )}

      <button
        onClick={() => zeon.submit(values)}
        style={{
          marginTop: 14, width: "100%", padding: "8px",
          background: "#1d4ed8", color: "#fff", border: "none",
          borderRadius: 4, fontSize: 13, cursor: "pointer", fontWeight: "bold",
        }}
      >
        Submit
      </button>
    </div>
  );
}
```

## Wiring in the workflow

`workflows/golden_gate_assembly_v2.json` ends with:

```json
"canvas_ui": {
  "kind": "react",
  "source_ref": "canvas/golden_gate_assembly_v2_screen.tsx",
  "enabled": true,
  "version": 2,
  "updated_at": "2026-05-16T00:00:00.000Z"
}
```

## Patterns to learn from

- **Default-exported function component** named `GoldenGateAssemblyV2Screen` (PascalCase + `Screen` suffix — convention matches `_pascal_case(workflow_id) + "Screen"`).
- **Imports only `react`** — `useState` plus the default. No other libraries (sandbox blocks them).
- **`declare const zeon: {...}`** is the TypeScript shape of the host-injected global. The actual runtime injects this; the `declare` is just for the type checker.
- **Iterates `zeon.schema`** rather than hardcoding input names. When the workflow's `inputs` change, the canvas adapts.
- **Per-`input.type` widget dispatch**:
  - `"object"` → `<select>` over `zeon.worldObjects` if non-empty, else text input fallback.
  - `"string"` → plain text input.
  - default (covers `"int"`, `"float"`, etc.) → `<input type="number" step="any">`.
- **`title={input.description}`** on each label — surfaces the workflow input's description as a tooltip.
- **Submit button calls `zeon.submit(values)`** — that's all it takes to launch the workflow. The host validates `values` against the workflow's inputs schema before starting the graph.
- **`zeon.onValidationErrors(setErrors)`** wires server-side validation errors back into the form.
- **Inline styles via `style={{ ... }}`** — no external CSS, the sandbox doesn't load stylesheets.

## When to author a custom canvas vs use the auto-form

- **Custom**: when the user wants a specific layout, grouping, or value-derivation logic for inputs.
- **Auto-form**: when you just need each `inputs[]` entry collected — set `canvas_ui.enabled: false` or remove the `canvas_ui` block entirely and the platform renders a default form.

## What the skill must do when generating a canvas

1. Run `scripts/invoke_scaffold.py item canvas <workflow_id>` — emits the minimal stub at `canvas/<workflow_id>_screen.tsx` with a `TODO` body.
2. Read the workflow's `inputs[]` via `scripts/extract_workflow_inputs.py`.
3. Replace the TODO body with the iteration shown above (or a custom layout the user asked for).
4. Edit the workflow JSON to add `canvas_ui` pointing at the new TSX file (T2 operation: diff + confirmation).
5. Bump `canvas_ui.version` on every subsequent edit.
