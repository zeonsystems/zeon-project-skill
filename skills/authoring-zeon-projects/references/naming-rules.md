# Naming rules

Rules taken from the on-disk schemas of `everything-prototype-containers`. Apply *all* of these before writing any file path or identifier; reject user input that fails them, don't silently rewrite.

## Item names (skill / workflow / world / object folder names)

Regex: `^[a-z_][a-z0-9_-]{0,63}$`

- Start with lowercase letter or underscore.
- Followed by lowercase letters, digits, underscores, or hyphens.
- 1 to 64 characters total.
- No spaces, uppercase letters, or other punctuation.

Source: `everything-prototype-containers/libraries/zeon_project_scaffold/src/zeon_project_scaffold/_scaffold.py:34` (`_NAME_RE`, applied in `validate_item_name()`).

### Folder names use the slug as-is

```
skills/<name>/
workflows/<name>.json
worlds/<name>/
objects/<name>/
```

### Python identifiers

Dashes in item names are illegal in Python identifiers, so when generating a skill's `robotic_code.py` function name, **replace `-` with `_`**:

| Folder | Python function |
|---|---|
| `pick_place` | `def pick_place(...)` |
| `pick-place` | `def pick_place(...)` ← still underscores |
| `tap_plate_v2` | `def tap_plate_v2(...)` |

Source: `_scaffold.py:52` (`_py_identifier()`).

The `skill_id` field inside `metadata.yaml` keeps the *original* slug (with dashes if any). Only the Python function name gets the substitution.

## `skill_id` (inside `metadata.yaml`)

Stricter regex: `^[a-z0-9_]+$` — **no dashes allowed**, no leading underscore enforced by the field validator.

Source: `libraries/protocol_schema/src/protocol_schema/skill_metadata.py:296-329` (`validate_skill_id_format`). This is enforced at load time by the Pydantic validator and prevents path traversal.

**Net rule for skills**: if you allow folder names with dashes, the inner `skill_id` field must use only `[a-z0-9_]`. The two values may differ (folder `tap-plate`, metadata `tap_plate`). Prefer matching them by using underscores in the folder name from the start.

## `workflow_id` (inside workflow JSON)

Pattern: `^[a-z0-9_]+$` — same as skill_id, no dashes.

Source: `services/gateway/src/gateway/routers/workflows.py:46` (`WORKFLOW_ID_PATTERN`), `docs/structure-templates/workflow/schema.json:22`.

The workflow JSON filename should match `workflows/<workflow_id>.json`.

## Node IDs (inside workflow JSON)

Pattern: `^[a-z0-9_]+$`.

The canonical convention emitted by `zeon_project_scaffold._scaffold._workflow_files` and the bundled `pick_place.json` example uses **short, semantic names** — one per role:

| Node | node_id |
|---|---|
| start | `start` |
| skill (pick) | `grab` |
| skill (move) | `move` |
| skill (drop) | `drop` |
| end | `end` |

If two nodes would collide (e.g. two `grab` nodes), disambiguate with a suffix (`grab_a`, `grab_b`) or by including the skill id (`grab_object_1`, `grab_object_2`). Keep IDs short and human-readable; the regex is the only hard rule.

Source: `everything-prototype-containers/libraries/zeon_project_scaffold/src/zeon_project_scaffold/_scaffold.py:283-309` and `templates/default/workflows/pick_place.json`.

## Edge IDs (inside workflow JSON)

Pattern: `^e\d+$` — short prefix.

Examples: `e0`, `e1`, `e12`.

This matches `zeon_project_scaffold._scaffold._workflow_files` and the bundled `pick_place.json` example. Earlier docs (and some older parts of the gateway) used `^edge_\d+$` — that form is no longer canonical.

Source: `everything-prototype-containers/libraries/zeon_project_scaffold/src/zeon_project_scaffold/_scaffold.py:300-307`.

## Parameter names (inside `metadata.yaml`)

Pattern: `^[a-z0-9_]+$` (snake_case alphanumeric + underscores). Enforced by `SkillParameter.validate_parameter_name_format`.

Source: `skill_metadata.py:87-111`.

## Input names (inside workflow JSON)

Pattern: `^[A-Za-z][A-Za-z0-9_]*$` — letters/numbers/underscores, **start with letter**. Both PascalCase and snake_case are accepted; pick one and stay consistent within a workflow.

Source: `services/gateway/src/gateway/routers/workflows.py:143`.

## Semantic version

Pattern: `^\d+\.\d+\.\d+$` (X.Y.Z, all integers).

Used by: workflow `version`, skill `version`. Both enforced.

Sources: `skill_metadata.py:331-356`, `services/gateway/src/gateway/routers/workflows.py` workflow validators, `docs/structure-templates/workflow/schema.json:35`.

## Timestamps

ISO 8601 with timezone. Example: `2026-05-19T12:34:56.000Z`.

Used in: `project.json` (created_at/updated_at), workflow JSON (created_at/updated_at, last_simulation_timestamp), world metadata.

When writing fresh timestamps, use Python `datetime.now(timezone.utc).isoformat()` with the trailing `Z` if you want to match the example.

## Canvas source_ref

Pattern: `^canvas/[a-z0-9_]+\.tsx$` — must point inside the `canvas/` folder, lowercase-alphanumeric filename, `.tsx` extension.

Source: `services/gateway/src/gateway/routers/workflows.py:50` (`CANVAS_REF_PATTERN`), `docs/structure-templates/workflow/schema.json:461`.

## Project folder slug

The project folder on disk (e.g. `golden-gate-assembly-mp6n1k2x`) is `<slug>-<8char random suffix>`. The `<slug>` is the human name of the project (kebab-case-friendly); the suffix is generated by the platform when a project is created (not authored by hand).

When **creating a project from inside the skill**:

- If the user is in an empty named directory (`mkdir my-bot && cd my-bot`), keep the user's folder name; don't append a random suffix.
- If the user is in a directory with no clear name (`cd /tmp/x`), ask for the project name and *suggest* a slug; do not invent a suffix.
- The `project.json` `name` field carries the **slug only** (no suffix). The suffix is platform metadata, not project content.

## Anything that looks like a name but isn't covered above

Default to: `^[a-z][a-z0-9_]{0,63}$` (snake_case alphanumeric, starts with letter, ≤64 chars). If a Pydantic validator rejects something looser, the field is stricter than this default — never looser.

## Red flags

- Uppercase characters in any id field (other than workflow `inputs[].name`). → reject.
- Spaces or punctuation other than `_` and `-` in slugs. → reject.
- Edge ids that don't match `e\d+`. → write `e<index>` instead.
- Long node ids that embed the workflow id (`start_<workflow>_0`). → use the short semantic form (`start`, `grab`, `end`).
- Generating random suffixes for project folders. → don't; let the platform.
- "Version 2" / "v2" inside an item name. → fine in `name`/`description`; in `skill_id`/`workflow_id`, only as `_v2`, never as a free-form suffix.
