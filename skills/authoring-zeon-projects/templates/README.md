# Templates

These templates are the **embedded fallback** used by `scripts/invoke_scaffold.py` when the official `zeon_project_scaffold` Python package is not importable on the user's machine.

## Layout

The folder mirrors a real Zeon project's layout so the mapping from template → output is obvious:

```
templates/
├── CLAUDE.md                                     # → CLAUDE.md  (project notes)
├── project.json                                  # → <project_root>/project.json
├── canvas/
│   ├── README.md                                 # → canvas/README.md
│   └── {workflow_id}_screen.tsx                  # → canvas/<workflow_id>_screen.tsx
├── data/                                         # optional, empty by default
│   └── .gitkeep
├── docs/                                         # optional, empty by default
│   └── .gitkeep
├── scripts/                                      # optional, empty by default
│   └── .gitkeep
├── skills/
│   └── {name}/                                   # → skills/<name>/
│       ├── metadata.yaml
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

There is no `inputs/` folder; it is deprecated. Skills no longer ship a `modules.py`; `robotic_code.py` imports `execution.skill_editing.execution_functions` directly.

`{name}` and `{canvas_id}` in folder/file names are literal placeholders — when the scaffold script copies a template, it substitutes them in both the path AND the file content.

## Placeholders

Substituted by `scripts/invoke_scaffold.py` at copy time:

| Placeholder | Replaced with |
|---|---|
| `{name}` | The item name (validated by `naming-rules.md`). Substituted in folder names, file names, AND content. |
| `{py_name}` | The item name with `-` → `_` (legal Python identifier). For skills only; content-only. |
| `{now}` | ISO-8601 timestamp at write time. For `project.json` and workflows; content-only. |
| `{workflow_id}` | The id of the workflow the canvas is attached to. Substituted in the canvas TSX filename AND in the TSX body. |
| `{component}` | TSX component name (PascalCase form of `{workflow_id}` + `Screen`). Auto-derived; content-only. |

The substitution is positional `str.replace`, not Python `.format()` — the JSON / YAML / TSX templates contain literal `{` and `}` braces that `.format()` would choke on.

## Convergence with `zeon_project_scaffold`

These templates are byte-identical to what the current `zeon_project_scaffold._scaffold` library emits via `iter_default_project_files()` and `item_template()` — same field set, same field order, same node/edge shapes. The library is the authoritative source.

There is one user-stated deprecation the library still ships but this skill omits: the `--global-object` parameter for object items. The user marked it deprecated; this skill never emits the `global_object` line. If you regenerate templates from the library, leave it out.
