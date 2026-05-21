---
name: authoring-zeon-projects
description: Use when the user is creating, extending, or refactoring a Zeon (everything-prototype-containers) project — anything involving project.json, skills, workflows, worlds, objects, or canvases — or when invoked inside a folder that already contains project.json and the standard subfolders (canvas/ data/ docs/ objects/ scripts/ skills/ workflows/ worlds/).
---

# Authoring Zeon projects

The Zeon platform ingests projects with a strict layout and tightly-validated schemas. Authoring by hand is error-prone — there are five distinct file formats, each with its own constraints and cross-references. This skill guides the user through creating new projects or extending existing ones, with structure guaranteed by either the official `zeon_project_scaffold` library (when installed) or the embedded fallback templates and schemas bundled here.

## First action: detect mode

Run `scripts/detect_project.py` from the user's current working directory. It returns one of:

- **`create`** — empty directory. Route to **Create mode** below.
- **`develop`** — has `project.json` and ≥ 1 standard subfolder. Route to `flows/develop-mode.md`.
- **`project_json_only`** — has `project.json` but no subfolders. Treat as develop mode and offer to scaffold missing subfolders.
- **`foreign`** — directory has files but no `project.json`. **Stop.** Tell the user this directory is not a Zeon project and ask whether they meant to `cd` elsewhere. Do not create files unless they confirm.

Echo to the user which mode you detected and why.

## Source-of-truth resolution

Every file-generating action goes through `scripts/invoke_scaffold.py`, which:

1. Tries to import `zeon_project_scaffold._scaffold`. Searches default `sys.path`, then `$ZEON_REPO`, then common locations.
2. If found: uses the library directly (single source of truth). Stderr prints `using=library`.
3. If not found: uses the embedded `templates/` (kept byte-aligned with the library's current output). Stderr prints `using=embedded`.

Echo `using=...` to the user so they know which path was taken.

The two paths produce equivalent output: same fields, same field order, same shapes. See `templates/README.md` for the embedded layout and `references/schema-*.md` for each file's schema.

## Create mode (brand-new project)

When `detect_project.py` returns `create`:

1. **Interview** the user (one question at a time, multiple-choice when possible):
   - "What is this project for?" (one-sentence summary)
   - "What's the project's slug?" (kebab-case or snake_case). Suggest one from the cwd folder name; confirm.
   - "Will the project have a workflow on day one, or do you want to start empty?"
   - If workflow-on-day-one: collect the workflow's name and rough sequence. Then check whether the skills it needs already exist — if not, list them as TODOs.
   - "Do you want an active_world now, or fill it in later?"
2. **Scaffold** by running `scripts/invoke_scaffold.py default`, then editing `project.json` with the user-supplied name + description.
3. **Handle the default examples**. When `using=library`, the scaffolder ships example skills (`grab_object`, `move_object`, `drop_object`), an example workflow (`pick_place`), and an example world (`bowl_bottle`) so a fresh project boots out of the box. Ask the user explicitly: **"Keep these examples as reference, or remove them so the project starts clean?"** Default: remove them when the user has named their own items in step 1; keep them when the user wants to start exploring. Either way, the answer goes through T1 ceremony — list which files would be deleted before deleting any.
4. **Loop into per-item authoring** for any items the user mentioned. For each, route to the matching `flows/authoring-*.md`.
5. **Validate** with `scripts/validate_project.py`. Surface output.

The default scaffold creates empty top-level subfolders. `data/`, `scripts/`, `docs/` stay empty — populate them only when the user has actual content for them.

## Risk tiers (always apply)

Every file operation falls into one of three tiers. The ceremony scales with risk.

| Tier | What | Ceremony |
|---|---|---|
| **T1 — Add new file** | A new skill / workflow / world / object / canvas not present before. | Ask the interview questions for the item type. After the user has answered, generate. Show file paths after writing. |
| **T2 — Modify existing file** | Edit a field in an existing file. | Read current → propose change → show **unified diff** → wait for explicit confirmation → `Edit`. |
| **T3 — Refactor / cross-file** | Rename, version bump, anything touching multiple files. | Route to `flows/refactor-flow.md`. Full change plan up front, explicit confirmation, sequential application. |

Pause indefinitely on T2/T3 — never proceed on silence.

## Flows

| Task | Flow |
|---|---|
| Develop-mode router | `flows/develop-mode.md` |
| Add a new skill | `flows/authoring-skill.md` |
| Add a new workflow | `flows/authoring-workflow.md` |
| Add a new world | `flows/authoring-world.md` |
| Add a new object | `flows/authoring-object.md` |
| Add a canvas to a workflow | `flows/authoring-canvas.md` |
| Rename / version bump / cross-file | `flows/refactor-flow.md` |

Load these on demand — don't load all of them at once.

## References (read when authoring)

| Need | File |
|---|---|
| Name regex / snake_case / version pattern / timestamp | `references/naming-rules.md` |
| `project.json` | `references/schema-project.md` |
| `metadata.yaml` + `robotic_code.py` | `references/schema-skill.md` |
| `workflows/<id>.json` | `references/schema-workflow.md` |
| `worlds/<name>/world_state.json` | `references/schema-world.md` |
| `objects/<name>/*.urdf` + `*.object_model.yaml` | `references/schema-object.md` |
| `canvas/<workflow_id>_screen.tsx` | `references/schema-canvas.md` |
| Execution functions for skill bodies | `references/execution-functions.md` |

## Red flags — stop and re-check

These thoughts mean you're about to make something break:

- **"I'll just make up a reasonable default for this field."** Don't. Ask the user, or leave the field absent if optional. Invented defaults (`workspace_aabb_min`, `attachment_spec.fit_type`, `collision_cache`) silently produce broken projects.
- **"I'll use `node_type` / `graph_id` for the workflow file."** The on-disk Workflow format uses `type` / `workflow_id`. The Pydantic `ExecutionGraph` is a different layer.
- **"This function name sounds plausible (`rotate_joint_6`, `pour_liquid`)."** If it's not in `references/execution-functions.md` or in an existing skill in this project, **don't write it**. Invented names crash at runtime.
- **"The edge IDs should be `edge_0`, `edge_1`."** No. The scaffold and the bundled `pick_place.json` use the short form `e0`, `e1` (regex `^e\d+$`). The earlier `edge_<n>` convention is outdated.
- **"I'll author the `.bin` / `.npz` / `.obj` / `.stl` placeholder."** No. Binary files are produced by the scanner / live in the mesh database. The skill creates text files only.
- **"I'll bump `version` since I changed the workflow."** Version bumps are explicit user intent. Reset `simulation_validated: false`, but only bump `version` when the user asks.
- **"This is just a quick rename — I'll skip the change plan."** Refactors are T3. Show the plan, wait for confirmation.

## Rationalization table

| Excuse | Reality |
|---|---|
| "The example uses X so X must be right." | Examples can be off-spec. The schemas in `references/` are authoritative; cite them. |
| "The user can fix it later if I'm wrong." | They probably can't — silent schema breakage shows up as a cryptic load error long after authoring. Validate before claiming done. |
| "It's just a placeholder, exact content doesn't matter." | Empty placeholders are fine; *wrong* placeholders are silent landmines. Use the templates as-is, don't ad-lib. |
| "I'll do all the edits in one big diff." | One operation per Edit. Multi-file refactors get a change plan, then sequential application, each confirmed. |
| "I don't need to run validate_project.py — I followed the schemas." | Run it. The validator catches what eyes miss: edge IDs, cross-refs, missing `objects: []`. Evidence before assertions. |
| "I'll invent a UUID / random suffix because the example has one." | UUIDs in world object keys: generate with `uuid.uuid4()`. Project folder random suffixes: don't invent — the platform adds those. |

## After every action

- Re-run `scripts/validate_project.py` and show the output.
- Don't say "done" or "fixed" without the validator's pass-output as evidence.
- Suggest commit groupings + messages at the end of the session. **Never commit yourself** (per the user's CLAUDE.md).

## Don't

- Don't create documentation files (`README.md`, `*.md`) unless the user asks.
- Don't auto-fix validator errors without confirmation. Surface them, propose options, wait.
- Don't combine flows in one operation (e.g. "add a skill AND wire it into the workflow"). Sequence them: add skill → confirm → add to workflow (T2) → confirm.
- Don't claim something works without having actually run the validator or — for canvases — actually opened it in a browser sandbox.
