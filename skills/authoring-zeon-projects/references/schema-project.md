# `project.json` schema

The top-level project manifest. **There is no Pydantic model enforcing this file** — the runtime reads it as a plain dictionary (`services/gateway/src/gateway/active_project.py:99-115`). Treat the fields below as the conventional shape used by every example and the canonical scaffolder.

## Required fields

| Field | Type | Notes |
|---|---|---|
| `name` | string | Project slug. Kebab-case-friendly, no random suffix. Example: `golden-gate-assembly`. |
| `description` | string | One-line summary. May be empty `""` for fresh projects. |
| `active_workflow` | string | Default workflow on load. Must match `workflow_id` of a file in `workflows/<active_workflow>.json`. May be empty `""` if the project has no workflows yet. |
| `active_world` | string | Default world on load. Must match the folder name `worlds/<active_world>/`. May be empty `""` if no world. |

## Conventional optional fields (seen in examples)

| Field | Type | Notes |
|---|---|---|
| `created_at` | ISO-8601 string | Set on creation, never updated. |
| `updated_at` | ISO-8601 string | Bump on every save. |
| `archived` | boolean | Defaults `false`. Set `true` to soft-delete. |

## Authoritative template

The official scaffolder emits this (after blanking `created_at`/`updated_at`/`archived`, which the platform adds at creation time):

```json
{
  "name": "",
  "description": "",
  "active_workflow": "pick_place",
  "active_world": "bowl_bottle"
}
```

Source: `everything-prototype-containers/libraries/zeon_project_scaffold/src/zeon_project_scaffold/templates/default/project.json`.

Note that the default scaffold's `active_workflow` and `active_world` point at the **example items it ships with**, so a fresh scaffold is runnable out of the box.

## Consistency rules the skill must enforce

When writing or modifying `project.json`:

1. If `active_workflow` is non-empty, `workflows/<active_workflow>.json` MUST exist; reject (or offer to scaffold the workflow) if it doesn't.
2. If `active_world` is non-empty, `worlds/<active_world>/world_state.json` MUST exist; same handling.
3. The values are filename stems, **not paths** and not with `.json` extension.
4. The `name` field's slug rules: `^[a-z][a-z0-9_-]{0,63}$` — same as item names (see `naming-rules.md`). Do not include the platform-generated random suffix in this field.

## When you're not sure whether to populate a field

- `created_at` / `updated_at`: include them on every write you do, with the current UTC timestamp in ISO-8601.
- `archived`: include only when explicitly set to `true`. If you're creating fresh, omit it (the runtime treats missing as `false`).

## What NOT to put in `project.json`

- A list of skills, workflows, worlds, or objects — the runtime discovers them by listing folders. Don't synthesize a registry.
- A `version` field — there isn't one. Versioning is per-workflow and per-skill.
- Paths to external resources — paths are relative to the project root by convention; full paths break portability.
