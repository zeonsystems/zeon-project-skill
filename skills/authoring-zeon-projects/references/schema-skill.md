# Skill schema

A skill is a folder under `skills/<skill_id>/` containing three files:

```
skills/<skill_id>/
├── metadata.yaml      # required — Pydantic-validated
├── robotic_code.py    # required — the actual Python implementation
└── modules.py         # required — shim importing execution functions
```

Validated at runtime by `libraries/skill_catalog/src/skill_catalog/metadata_loader.py:155-305` (Pydantic via `SkillMetadata.model_validate`).

---

## `metadata.yaml`

Pydantic source-of-truth: `libraries/protocol_schema/src/protocol_schema/skill_metadata.py:221-417` (`SkillMetadata`).

### Required fields

| Field | Type | Constraint |
|---|---|---|
| `skill_id` | string | Pattern `^[a-z0-9_]+$`. Must match the folder name (modulo dashes — see `naming-rules.md`). Path-traversal safe. |
| `version` | string | Semantic version `^\d+\.\d+\.\d+$`. |
| `description` | string | One-line human description. |

### Optional fields (with defaults)

| Field | Type | Default | Notes |
|---|---|---|---|
| `parameters` | list[SkillParameter] | `[]` | See `SkillParameter` below. May be omitted entirely if the AST-derived signature is sufficient. |
| `preconditions` | dict[str, any] | `{}` | Key-value pairs documenting required state before execution. Free-form keys. |
| `postconditions` | dict[str, any] | `{}` | Key-value pairs the skill promises to establish on success. |
| `safety_rules` | list[str] | `[]` | Human-readable safety constraints (free-form strings). |
| `tags` | list[str] | `[]` | Free-form discovery labels. |
| `high_risk` | bool | `false` | If `true`, runtime auto-inserts checkpoints before execution. |
| `world_state_prime` | dict \| null | `null` | Initial scene-state override. Rarely set by humans; the scanner produces it. |
| `parameter_descriptions` | dict[str, str] | `{}` | Override the docstring-derived parameter descriptions, keyed by parameter name. |

### `SkillParameter` shape

Each entry in `parameters`:

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | required | Pattern `^[a-z0-9_]+$`. |
| `type` | enum | required | One of `string`, `float`, `int`, `boolean`, `object`, `array`. |
| `description` | string | required | Human description (shown in canvases). |
| `required` | bool | `true` | If `true`, `default` must be omitted/null. |
| `default` | any | `null` | Value used when `required: false`. Type must match `type`. |
| `object_schema` | dict[str, SkillParameter] | `null` | Recursive nested schema for `type: object`. |
| `array_item_type` | enum | `null` | Item type for `type: array`. |

Validators (raise at load time):
- `name` snake_case alphanumeric.
- `required: true` ⇒ no `default`.
- `default` type must match `type` (string→str, float→float/int, int→int, boolean→bool, array→list/tuple, object→dict).
- Circular precondition (skill can't depend on itself).

### AST-driven parameter derivation

The loader can derive `parameters` **automatically from the Python function signature** in `robotic_code.py`. See `metadata_loader.py:155-305` → `resolve_skill_parameters()` → `parameters_from_signature()`.

This means a skill that just lists params on the function signature with type hints does NOT need to repeat them in `metadata.yaml`. If `metadata.yaml.parameters` is omitted or `[]`, the loader inspects the function's AST.

Type-hint → `ParameterType` mapping:

| Python annotation | `ParameterType` |
|---|---|
| `str` | `string` |
| `int` | `int` |
| `float` | `float` |
| `bool` | `boolean` |
| `SkillObject` (from `protocol_schema`) | `object` |
| `list`, `tuple`, `Sequence` | `array` |
| `dict`, `Dict`, `Mapping` | `object` |

If the annotation is missing, the loader falls back to the type of the default value.

Docstring `Args:` block (Google style) provides descriptions; `parameter_descriptions` in YAML overrides them.

**Practical guidance**:
- For simple skills, omit `parameters` from YAML and let the AST do the work.
- Include `parameters` when you need fields the AST cannot infer: `description`, `required: false` with `default`, `object_schema`, `array_item_type`.

### Minimal valid `metadata.yaml`

```yaml
skill_id: my_skill
version: "1.0.0"
description: "What this skill does, in one sentence."
```

### Fully populated example

```yaml
skill_id: pick_object
version: "1.0.0"
description: "Pick up an object using the gripper."

parameters:
  - name: object_id
    type: string
    description: "ID of the object to pick."
    required: true
  - name: force
    type: float
    description: "Grip force in Newtons."
    required: false
    default: 50.0

preconditions:
  camera_calibrated: true
  gripper_open: true

postconditions:
  object_grasped: true

safety_rules:
  - "Maximum grip force: 80.0N"
  - "Collision detection enabled"

tags:
  - manipulation
  - gripper

high_risk: false
```

---

## `robotic_code.py`

The implementation file. The loader does NOT import this module at metadata-load time; it inspects it via AST so parameter introspection is safe even if imports would fail.

At execution time, the executor imports the module from `<project_root>/skills/<skill_id>/robotic_code` and calls the function whose name matches the skill_id (with dashes converted to underscores).

### Required shape

```python
from .modules import *
from protocol_schema import SkillObject  # if any parameter is a SkillObject

OBJECT_VARIABLES = {}  # see note below


def <skill_id>(<typed params with defaults>):
    """One-line summary.

    Args:
        param_name: Description.
        ...
    """
    # implementation
    return {"success": True}  # or failure shape
```

Notes:
- The function name MUST match the skill_id with dashes replaced by underscores (see `naming-rules.md`).
- `OBJECT_VARIABLES = {}` at module scope: emitted by the official scaffold template. It is a module-level slot used by the legacy parameter-binding pathway (skills that didn't yet use `SkillObject` parameters). Keep it as `{}` for new skills; the modern `SkillObject` signature pattern doesn't read from it.
- Type hints are **strongly recommended** so AST parameter inference works.
- Return value should be a dict; `{"success": True}` for success. Failure modes vary across skills — look at neighbours if unsure.
- Use `from .modules import *` to get execution functions and any per-skill helpers.
- For object parameters, use `SkillObject` from `protocol_schema` (a frozen dataclass with `id: str` and `pose: List[float]` — 12-element pose).

### `SkillObject` type (from `protocol_schema.skill_io`)

```python
from protocol_schema import SkillObject

def my_skill(plate: SkillObject, anchor: str = "A1"):
    plate.id      # world-object UUID
    plate.pose    # 12-floats: [cx, cy, cz, roll, pitch, yaw, ex, ey, ez, ox, oy, oz]
```

Anchors are referenced by name (string); see `schema-object.md` for the anchor list.

### Cross-skill imports (composition / "super-skills")

A skill can call another skill in the same project:

```python
from sibling_skill.robotic_code import sibling_skill
```

The project loader places `skills/` on `sys.path` so sibling-skill imports resolve.

This is the standard pattern for "super skills" that orchestrate sequences of smaller skills.

---

## `modules.py`

Bridges your skill to the runtime's execution functions. Almost always exactly one line:

```python
from execution.skill_editing.execution_functions import *
```

This re-exports everything in the platform's execution-functions API (motion, gripper, perception primitives) under your skill's `modules` namespace.

If your skill needs additional helpers private to it, define them in `modules.py` below the import. The convention is small helpers in `modules.py`, public skill entry in `robotic_code.py`.

### What's available after `import *`

The execution-functions module's exports are project-runtime-dependent. **Do not invent function names**. When authoring a new skill:

1. If the user has filled in `references/execution-functions.md`, use the functions documented there.
2. Otherwise, check existing skills in the same project for working examples (`grep -r "def " skills/<other_skill>/robotic_code.py`).
3. If a function you need isn't documented and isn't in any existing skill, **ask the user** rather than guessing — invented function names will fail at execution time with `NameError`.

---

## Validation the skill should run after writing

1. `metadata.yaml` parses as YAML.
2. `SkillMetadata.model_validate(yaml.safe_load(open(path)))` passes — invoke via `python -c` when `protocol_schema` is importable; otherwise validate manually against the rules above.
3. `robotic_code.py` parses as Python (`ast.parse` succeeds).
4. The function name in `robotic_code.py` matches `_py_identifier(skill_id)`.
5. Parameter types in the signature are valid Python type hints.
6. `modules.py` contains at least the `from execution.skill_editing.execution_functions import *` line.

## Common mistakes

- Putting the description in `description:` as multi-paragraph prose. Keep it to one line.
- Setting `required: true` AND providing a `default` — fails Pydantic validation.
- Using camelCase parameter names — fails the snake_case validator.
- Forgetting `from .modules import *` — the function will fail at execution due to missing globals.
- Cross-skill imports of `.robotic_code` from outside the project root — only works if `skills/` is on `sys.path` (it is, at execution time).
- Inventing execution-function names — every invented name is a runtime crash.
