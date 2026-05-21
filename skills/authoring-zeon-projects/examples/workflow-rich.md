# Example: rich workflow (many skills + canvas)

This is the active workflow from `golden-gate-assembly`, `golden_gate_assembly_v2.json`. It runs 11 skills end-to-end, has 15 inputs (10 objects + 4 strings + 1 float), and attaches a custom canvas.

Source: `golden-gate-assembly-mp6n1k2x/workflows/golden_gate_assembly_v2.json` — go read it directly for the full content; this file extracts the most instructive sections.

## Header + inputs (first ~30 lines)

```json
{
  "workflow_id": "golden_gate_assembly_v2",
  "name": "Golden Gate Assembly v2",
  "description": "Full GG assembly: MM prep, plate map, dispense MM/water/parts, seal plate (individual steps), platefuge spin, thermocycler run (individual steps).",
  "version": "1.0.0",
  "author": "bkolar",
  "created_at": "2026-05-16T00:00:00.000Z",
  "updated_at": "2026-05-16T00:00:00.000Z",
  "simulation_validated": false,
  "objects": [],
  "inputs": [
    { "name": "reaction_plate",  "type": "object", "is_array": false, "description": "Reaction Plate (PCR)" },
    { "name": "parts_plate",     "type": "object", "is_array": false, "description": "Parts Plate (PCR)" },
    { "name": "di_water_source", "type": "object", "is_array": false, "description": "DI Water cold block" },
    { "name": "nebr_source",     "type": "object", "is_array": false, "description": "NEB R Ligase MM Source" },
    { "name": "bsai_source",     "type": "object", "is_array": false, "description": "BsaI Source" },
    { "name": "mm_cold_block",   "type": "object", "is_array": false, "description": "Master Mix Cold Block" },
    { "name": "plate_sealer",    "type": "object", "is_array": false, "description": "Plate Sealer" },
    { "name": "seal_holder",     "type": "object", "is_array": false, "description": "Seal Holder (stacked)" },
    { "name": "plate_stand",     "type": "object", "is_array": false, "description": "Plate Stand" },
    { "name": "thermocycler",    "type": "object", "is_array": false, "description": "Eppendorf Thermocycler" },
    { "name": "di_water_anchor","type": "string", "description": "Hole anchor for DI water on its cold block", "defaultValue": "hole_1" },
    { "name": "nebr_anchor",    "type": "string", "description": "Hole anchor for NEB R ligase MM on its cold block", "defaultValue": "hole_1" },
    { "name": "bsai_anchor",    "type": "string", "description": "Hole anchor for BsaI on its cold block", "defaultValue": "hole_1" },
    { "name": "mm_anchor",      "type": "string", "description": "Hole anchor for master mix in mm_cold_block", "defaultValue": "hole_2" },
    { "name": "spin_duration",  "type": "float",  "description": "Platefuge spin time in seconds", "defaultValue": 300 }
  ],
```

## One representative skill node

A node that mixes input-bound parameters with a string literal:

```json
{
  "node_id": "mm_prep_2",
  "type": "skill",
  "label": "Prep Master Mix",
  "description": "Chunked aspirate/dispense of DI water, NEB R Ligase MM, and BsaI into cold block hole; mix 10× at 10µL",
  "skill_id": "mm_prep",
  "parameters": {
    "di_water_source": { "$input": "di_water_source" },
    "nebr_source":     { "$input": "nebr_source" },
    "bsai_source":     { "$input": "bsai_source" },
    "mm_cold_block":   { "$input": "mm_cold_block" },
    "di_water_anchor": { "$input": "di_water_anchor" },
    "nebr_anchor":     { "$input": "nebr_anchor" },
    "bsai_anchor":     { "$input": "bsai_anchor" },
    "mm_anchor":       { "$input": "mm_anchor" },
    "current_map":     "projects/golden-gate-assembly-mp6n1k2x/data/runs/current.json"
  }
}
```

## Canvas attachment (last block)

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

- **Many object inputs**: ten different world-objects the user selects at launch time. Each object input shows up as one row in the canvas's auto-generated or custom form.
- **String inputs with `defaultValue`**: the four `*_anchor` inputs default to `hole_1` / `hole_2`. Keeps the form usable while still letting the user override.
- **Float input with a sensible default**: `spin_duration: 300` (5 minutes).
- **Literal parameter values alongside input-bound ones**: `"current_map": "projects/..."` — a file-path literal. Anything JSON-encodable is fine as a parameter value.
- **Node descriptions**: each skill node has a `description` field beyond just `label`. Shows up in tooltips / detail views.
- **`canvas_ui.version: 2`**: this canvas has been edited once since first creation. Each save bumps the version (cache-bust key).
- **Node IDs follow `<skill_id>_<index>` form** in this workflow (e.g. `mm_prep_2`, `dispense_mm_4`). Alternative to the bare `mm_prep`/`dispense_mm` form. Pick one style and stay consistent within a workflow.

## When to author a workflow this big

- A real process / protocol with many steps that the user wants represented as one runnable unit.
- Each step is already factored into its own skill (the workflow is pure orchestration).
- Inputs are bound at launch (via the canvas or auto-form) so the same workflow can run against different objects each time.

## When to split

- If two halves of the workflow are independently useful, consider extracting one half into its own workflow.
- If a sub-sequence is always called identically, fold it into a super-skill (see `skill-super-calls-others.md`).
