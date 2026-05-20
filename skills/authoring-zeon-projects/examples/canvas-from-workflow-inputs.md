# Example: generating a canvas from a workflow's inputs

When a workflow has `inputs[]` and the user wants a bespoke form, generate the TSX from the inputs schema. The widgets map directly from `input.type`.

## Source workflow inputs

From `workflows/pick_target.json`:

```json
"inputs": [
  { "name": "target",    "type": "object", "description": "Object to pick.",         "is_array": false },
  { "name": "force_n",   "type": "float",  "description": "Grip force in Newtons.",  "default_value": 50.0 },
  { "name": "verify",    "type": "string", "description": "Run a verification pass after pick (yes/no).", "default_value": "no" }
]
```

## Generated `canvas/pick_target_screen.tsx`

```tsx
import React, { useState } from "react";

declare const zeon: {
  schema: { name: string; type: string; description?: string; defaultValue?: unknown }[];
  worldObjects: { uuid: string; name: string; displayName?: string }[];
  defaults: Record<string, unknown>;
  submit: (values: Record<string, unknown>) => void;
  onValidationErrors: (cb: (errs: { path: string; message: string }[]) => void) => void;
};

export default function PickTargetScreen() {
  const [values, setValues] = useState<Record<string, unknown>>(() => ({ ...zeon.defaults }));
  const [errors, setErrors] = useState<{ path: string; message: string }[]>([]);

  zeon.onValidationErrors(setErrors);

  const set = (name: string, val: unknown) =>
    setValues((v) => ({ ...v, [name]: val }));

  const s: React.CSSProperties = {
    width: "100%", padding: "5px 7px", fontSize: 13,
    border: "1px solid #ccc", borderRadius: 4, boxSizing: "border-box",
  };

  return (
    <div style={{ fontFamily: "monospace", padding: 16, maxWidth: 480 }}>
      <div style={{ marginBottom: 12, fontWeight: "bold" }}>Pick Target</div>

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
                <input type="text" placeholder="object name / id"
                  value={String(val ?? "")} onChange={(e) => set(input.name, e.target.value)} style={s} />
              )
            ) : input.type === "string" ? (
              <input type="text"
                value={String(val ?? "")} onChange={(e) => set(input.name, e.target.value)} style={s} />
            ) : (
              <input type="number" step="any"
                value={val === undefined || val === "" ? "" : Number(val)}
                onChange={(e) => set(input.name, e.target.value === "" ? "" : Number(e.target.value))}
                style={s} />
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

## Wiring it into the workflow

Update `workflows/pick_target.json`:

```json
"canvas_ui": {
  "kind": "react",
  "source_ref": "canvas/pick_target_screen.tsx",
  "enabled": true,
  "version": 1,
  "updated_at": "2026-05-19T12:00:00.000Z"
}
```

## Type → widget map

| `input.type` | Widget |
|---|---|
| `string` | `<input type="text">` |
| `int` | `<input type="number" step="1">` |
| `float` | `<input type="number" step="any">` |
| `object` | `<select>` from `zeon.worldObjects` (or text input fallback) |
| `structured` | JSON textarea — flag to user that a richer renderer would help |

For `is_array: true`, add a small list editor (add row / remove row); the boilerplate above doesn't include one.

## Things to verify

- The component name is unique and PascalCase (e.g. `PickTargetScreen`). It must not collide with React reserved names.
- The `source_ref` filename matches the actual file on disk.
- The workflow's `canvas_ui.version` is `1` for a new canvas, or bumped for an update.
- The TSX imports `react` only — no other libraries allowed in the sandbox.
