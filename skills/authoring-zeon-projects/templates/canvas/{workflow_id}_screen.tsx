import React, { useState } from "react";

declare const zeon: {
  schema: { name: string; type: string; description?: string; defaultValue?: unknown }[];
  worldObjects: { uuid: string; name: string; displayName?: string }[];
  defaults: Record<string, unknown>;
  submit: (values: Record<string, unknown>) => void;
  onValidationErrors: (cb: (errs: { path: string; message: string }[]) => void) => void;
};

export default function {component}() {
  const [values, setValues] = useState<Record<string, unknown>>(() => ({ ...zeon.defaults }));
  const [errors, setErrors] = useState<{ path: string; message: string }[]>([]);

  zeon.onValidationErrors(setErrors);

  // TODO: build the input UI for `{workflow_id}` here.
  // `zeon.schema` lists the workflow's declared inputs; collect values into
  // the `values` state and call `zeon.submit(values)` to run the workflow.
  return (
    <div style={{ fontFamily: "monospace", padding: 16 }}>
      <div style={{ marginBottom: 12, fontWeight: "bold" }}>{workflow_id}</div>

      {errors.length > 0 && (
        <div style={{ color: "red", fontSize: 12, marginBottom: 8 }}>
          {errors.map((e, i) => (
            <div key={i}>⚠ {e.path}: {e.message}</div>
          ))}
        </div>
      )}

      <button onClick={() => zeon.submit(values)}>Submit</button>
    </div>
  );
}
