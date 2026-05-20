# Templates

These templates are the **embedded fallback** used by `scripts/invoke_scaffold.py` when the official `zeon_project_scaffold` Python package is not importable on the user's machine.

## Layout

The folder mirrors a real Zeon project's layout so the mapping from template → output is obvious:

```
templates/
├── project.json                                  # → <project_root>/project.json
├── canvas/
│   ├── README.md                                 # → canvas/README.md
│   └── {canvas_id}.tsx                           # → canvas/<canvas_id>.tsx
├── data/                                         # optional, empty by default
│   └── .gitkeep
├── docs/                                         # optional, empty by default
│   └── .gitkeep
├── scripts/                                      # optional, empty by default
│   └── .gitkeep
├── skills/
│   └── {name}/                                   # → skills/<name>/
│       ├── metadata.yaml
│       ├── modules.py
│       └── robotic_code.py
├── workflows/
│   └── {name}.json                               # → workflows/<name>.json
├── worlds/
│   └── {name}/
│       └── world_state.json                      # → worlds/<name>/world_state.json
└── objects/
    └── {name}/
        ├── {name}.urdf                           # → objects/<name>/<name>.urdf
        └── {name}.object_model.yaml              # → objects/<name>/<name>.object_model.yaml
```

All 8 top-level folders are present — `canvas/`, `data/`, `docs/`, `scripts/`, `objects/`, `skills/`, `workflows/`, `worlds/`. The first four are optional in content (start empty) but always exist as folders. The last four are critical and may carry items.

There is no `inputs/` folder; it is deprecated.

`{name}` and `{canvas_id}` in folder/file names are literal placeholders — when the scaffold script copies a template, it substitutes them in both the path AND the file content.

## Placeholders

Substituted by `scripts/invoke_scaffold.py` at copy time:

| Placeholder | Replaced with |
|---|---|
| `{name}` | The item name (validated by `naming-rules.md`). Substituted in folder names, file names, AND content. |
| `{py_name}` | The item name with `-` → `_` (legal Python identifier). For skills only; content-only. |
| `{now}` | ISO-8601 timestamp at write time. For workflows; content-only. |
| `{component_name}` | TSX component name (PascalCase). For canvases; content-only. |
| `{title}` | Workflow display name. For canvases; content-only. |
| `{canvas_id}` | The canvas's id (`<workflow_id>_screen` by convention). Substituted in the TSX filename. |

The substitution is positional `str.replace`, not Python `.format()` — the JSON / YAML / TSX templates contain literal `{` and `}` braces that `.format()` would choke on.

## Divergence from `zeon_project_scaffold`

These templates intentionally differ from `zeon_project_scaffold._scaffold` in one place:

- **`workflows/{name}.json`** uses the **on-disk Workflow format** (`workflow_id`, `type` on nodes, nested `condition: {type: ...}`, edge ids `edge_<n>`) that the gateway loader actually accepts — see `references/schema-workflow.md` and `services/gateway/src/gateway/routers/workflows.py:60-220`.
- The library's `_workflow_files()` and bundled `templates/default/workflows/pick_place.json` both emit the older `ExecutionGraph` shape (`graph_id`, `node_type`, string `condition`). `scripts/invoke_scaffold.py` transforms library output to the on-disk shape on the fly via `_convert_workflow_eg_to_disk()`.

If you regenerate templates from the library, double-check these files and keep the embedded copies in the canonical Workflow format.
