# zeon-project-skill

A Claude Code plugin that helps you author, extend, and refactor projects for the [Zeon `everything-prototype-containers`](https://github.com/ZeonSystems/everything-prototype-containers) robotics / lab-automation platform.

Zeon projects have a strict layout:

```
my-project/
├── project.json
├── canvas/   data/   docs/   scripts/   (optional, populated as needed)
├── objects/<name>/{<name>.urdf, <name>.object_model.yaml}
├── skills/<id>/{metadata.yaml, robotic_code.py, modules.py}
├── workflows/<id>.json
└── worlds/<name>/world_state.json
```

This skill guarantees every file matches the canonical schema by:

1. **Preferring the real `zeon_project_scaffold` library** when the product repo is on disk or pip-installed (single source of truth, zero drift).
2. **Falling back to bundled schemas/templates** so it works on machines without the product.

## What it does

| Mode | When | What |
|---|---|---|
| **Create** | cwd has no `project.json` | Interviews you about project intent → scaffolds full layout → loops into per-item authoring. |
| **Develop** | cwd has `project.json` + standard subfolders | Analyses current state → adds, modifies, or refactors items with risk-tiered confirmation. |

Item types covered: project, skill, workflow, world, object, canvas.

## Install

### Via plugin marketplace

```
/plugin install zeon-project-skill
```

### Manually

```bash
git clone https://github.com/ZeonSystems/zeon-project-skill ~/.claude/plugins/zeon-project-skill
```

Then restart Claude Code. The skill `authoring-zeon-projects` becomes discoverable.

## Use

In any directory, ask Claude something like:

- "Scaffold a Zeon project for a tube-rack picking robot."
- "Add a skill called `tap_plate` to this project."
- "Rename my workflow `pick_v1` to `pick_and_place` and update everything that references it."
- "My `active_workflow` points to a missing file. Fix it."

The skill detects whether the cwd is a Zeon project and routes accordingly.

## Source-of-truth resolution

The skill checks for `zeon_project_scaffold` in this order:

1. Default Python import path.
2. `$ZEON_REPO` environment variable, pointing at a checkout of `everything-prototype-containers`.
3. Common locations: `~/code/everything-prototype-containers`, `~/GitHub/ZeonSystems/everything-prototype-containers`, etc.
4. A neighbour of the current directory containing `libraries/zeon_project_scaffold/`.

If none of these resolves, the skill uses the bundled templates and schema reference under `skills/authoring-zeon-projects/`.

When the library is available, its `workflows/*.json` output is transformed into the canonical on-disk Workflow format (the library currently emits the older `ExecutionGraph` shape; the gateway loader expects the Workflow shape). All other items pass through unchanged. The transformation runs in `scripts/invoke_scaffold.py`.

## What's in this repo

```
zeon-project-skill/
├── README.md
├── .claude-plugin/plugin.json
└── skills/authoring-zeon-projects/
    ├── SKILL.md            # entry point + create-mode flow + red flags
    ├── flows/              # develop-mode + per-item authoring + refactor
    ├── references/         # canonical schemas for every file type
    ├── templates/          # embedded fallback templates
    ├── examples/           # distilled, generic examples
    └── scripts/            # detect / scaffold / validate / extract_inputs
```

## Validation

Every project the skill produces (or modifies) gets validated by `scripts/validate_project.py`:

- Name regex on every item (`^[a-z_][a-z0-9_-]{0,63}$`).
- Required fields on `project.json`, workflow JSON, skill `metadata.yaml`, world `world_state.json`, object URDF + YAML.
- Cross-references: `active_workflow` → file exists, `active_world` → folder exists, `node.skill_id` → skill folder exists, `canvas_ui.source_ref` → TSX exists.
- Workflow structural rules: 1 start, ≥ 1 end, valid `type`, valid edge condition, conditional / loop nodes have 2 outgoing edges, no unintended cycles.
- Pydantic `SkillMetadata.model_validate` when `protocol_schema` is importable.

Errors block the skill from claiming "done"; warnings are surfaced.

## License

See [LICENSE](LICENSE) if present, otherwise default to "all rights reserved by the authors".
