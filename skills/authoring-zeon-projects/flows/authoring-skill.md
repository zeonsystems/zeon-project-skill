# Flow: author a new skill

A skill is a unit of robotic work. Two files in `skills/<skill_id>/`: `metadata.yaml` and `robotic_code.py`.

**Schemas**: `references/schema-skill.md`, `references/naming-rules.md`, `references/execution-functions.md`.

## Required information (interview)

Ask ONE question at a time. Don't bundle.

1. **What should the skill do?** (one-sentence summary)
2. **What is its `skill_id`?** (snake_case, lowercase alphanumeric + underscores). If they gave a kebab-case folder, propose the underscored skill_id and confirm.
3. **What parameters does it take?** For each:
   - Name (snake_case)
   - Type (string / int / float / boolean / object / array)
   - Required?
   - Default value if optional
   - Brief description
4. **If a parameter is `object` type**: does it represent a *world object* (use `SkillObject`) or *nested structured data* (use a dict)? Default to `SkillObject` for anything that lives in the world.
5. **Preconditions** (free-form key-value pairs of state assumed true before this runs). Optional.
6. **Postconditions** (state guaranteed true after success). Optional.
7. **Tags** for discovery. Optional.
8. **Is it high-risk?** (triggers checkpoints automatically). Default `false`.
9. **Should it call other skills?** If yes, list them — they must exist in the project. The skill becomes a super-skill (see `examples/skill-super-calls-others.md`).
10. **Implementation approach**: ask the user if they want
    - (a) A stub (`# TODO: Implement skill logic here.` and an empty body), or
    - (b) A first-pass implementation using `execution.skill_editing.execution_functions`.
    
    If (b): use functions documented in `references/execution-functions.md` (or, when that file is incomplete, functions you've confirmed exist in another skill in the same project). **Don't invent function names.** If unsure, fall back to (a) with a TODO and confirm with the user.

## Generation

1. Run `scripts/invoke_scaffold.py item skill <skill_id>`. Capture the file map (two files: `metadata.yaml` + `robotic_code.py`).
2. Decode the base64 contents.
3. Overlay user-provided fields on the templates:
   - `metadata.yaml`: fill `description`, `parameters` (only if the user wants explicit declarations rather than AST inference), `preconditions`, `postconditions`, `tags`, `high_risk`.
   - `robotic_code.py`: replace the stub body with the user-approved implementation. Update the function signature with typed parameters. Update the docstring `Args:` block.
4. Write the files via `Write` (new files; no need for `Edit`).

Private helpers belong inside `robotic_code.py` (above the public function) or in a sibling skill imported via `from <peer>.robotic_code import <peer>`. There is no `modules.py`.

## Decisions you must NOT make alone

- The skill's actual behaviour (what motion / state changes it performs). Ask.
- Whether to use `SkillObject` or another type for an object parameter. Ask if unclear.
- Function names from the execution-functions module that aren't documented. **Always ask if uncertain.**
- Whether to bypass `metadata.yaml.parameters` and let the AST do it. Default: omit `parameters` if the function signature is straightforward; include it only when needed (descriptions, optional with default, nested schemas).

## Validation

1. `python3 -c "import yaml; yaml.safe_load(open('skills/<id>/metadata.yaml'))"` parses.
2. `python3 -c "import ast; ast.parse(open('skills/<id>/robotic_code.py').read())"` parses.
3. Run `scripts/validate_project.py` from the project root.
4. If `protocol_schema` is importable, the validator runs `SkillMetadata.model_validate` — escalate any failure to the user.

## Cross-reference checks

- The skill's function name in `robotic_code.py` must equal `_py_identifier(skill_id)` (dashes → underscores).
- If the skill calls peer skills, each peer must exist at `skills/<peer_id>/`.
- If the skill is referenced from a workflow (`node.skill_id`), that workflow's node must be updated; the new-skill flow does not edit workflows. If the user wants to wire it in, route to "Modify" in `develop-mode.md` for the workflow.

## Common mistakes

- Inventing execution-function names. → ask, or stub with TODO.
- Adding parameters to `metadata.yaml` AND the function signature inconsistently (e.g. AST says one set, YAML says another). Pick one source of truth; prefer the function signature.
- Using `SkillObject` for non-world-object parameters (a wellplate row index, a volume — use `int` / `float`).
- Setting `required: true` while also providing `default`. Validation fails.
- Forgetting `from execution.skill_editing.execution_functions import *` at the top of robotic_code.py. The function will have no access to execution functions at runtime.
- Writing a `modules.py` next to `robotic_code.py`. Not part of the schema any more — the runtime does not look for it.

## After writing

- Re-run `scripts/validate_project.py` and surface the output.
- Show the user the new file paths and offer:
  - "Want to wire this skill into a workflow now?" → route to `authoring-workflow.md` (Modify) or a fresh workflow.
  - "Want to add a test or simulation?" → out of scope for this skill (suggest the user run the platform's verify CLI).
