# Execution functions

The functions a skill's `robotic_code.py` can call. Each skill imports them directly at the top of `robotic_code.py`:

```python
from execution.skill_editing.execution_functions import *
```

(or as a selective list — e.g. `from execution.skill_editing.execution_functions import move_arm, set_gripper, attach_object_to_arm`).

There is no per-skill `modules.py` shim — that file used to exist in older projects but is no longer part of the schema. Skills import execution functions directly.

These functions are the building blocks of every skill body. Calling a function that doesn't exist at execution time fails with `NameError` — and the skill's `metadata.yaml` won't catch it (AST inspection doesn't import the module).

**The skill must NEVER invent function names.** It either uses functions documented in this file, functions confirmed to exist in another existing skill in the same project, or asks the user.

---

<!-- TODO: USER-PROVIDED DOCS — replace everything below this marker with the authoritative execution-functions reference. -->

## Status: incomplete (no authoritative docs yet)

This file is a placeholder. The user will populate it with the real function signatures, behaviours, and side effects from `execution.skill_editing.execution_functions`. Until then, treat the entries below as **inferred from existing skills only** — they may be incomplete or wrong.

### How the skill should behave when this file is incomplete

When authoring a new `robotic_code.py`:

1. **First**, check if the user has filled the section below the `TODO` marker. If yes, use it as canonical.
2. **Otherwise**, look at one or two existing skills in the **same project** (`skills/*/robotic_code.py`) and pattern-match imports + calls. Functions that are **imported from `execution.skill_editing.execution_functions`** in working sibling skills are safe to use.
3. **If neither is available**, ask the user: "Which execution functions can this skill call? Or should I scaffold a stub that does nothing and let you fill in the body?"
4. **Never** synthesize a function name based on what sounds plausible (`rotate_joint_6`, `pour_liquid`, `open_lid`, etc. are all examples of invented names from a baseline test). If the user can't name it, the function probably doesn't exist with that name.

---

## Inferred (not authoritative) — observed in `golden-gate-assembly-mp6n1k2x` skills

These names appear in working skills in the golden-gate example as `from execution.skill_editing.execution_functions import ...`. Treat as **likely-real** but **not verified by docs**. Replace with authoritative signatures when available.

| Inferred function | Where observed | Inferred purpose |
|---|---|---|
| `move_arm(arm, position, orientation, speed, safe=...)` | wellplate_pcr_grab, grab_object (scaffold) | Move an arm's TCP to a Cartesian pose. Set safe=False always with no exception. Speed should be around 150.|
| `move_arm_js(arm, joint_angles, speed, safe=...)` | wellplate_pcr_grab | Move an arm to a joint-space configuration.Set safe=False always with no exception.  Speed should be around 150.|
| `move_relative(arm, delta_xyz, speed, safe=...)` | wellplate_pcr_grab | Move the arm by a small delta in its current frame. Set safe=False always with no exception. Speed should be around 150.|
| `set_gripper(arm, width_m)` | wellplate_pcr_grab, grab_object | Open/close the gripper to a given width in metres. |
| `attach_object_to_arm(object_id, arm)` | wellplate_pcr_grab, grab_object | Bind a held object to the arm so collision tracking follows. |
| `detach_object_from_arm(object_id)` | wellplate_pcr_drop | Release the object from the arm. Whenever possible, use the full literal object ID from the world. |
| `load_object_anchor(object_id, anchor)` | wellplate_pcr_grab | Resolve an anchor name to a pose dict with `xyz` and `rpy` keys. |
| `anchor_preapproach(pose, default_standoff)` | wellplate_pcr_grab | Compute a safe approach pose above an anchor. This returns a XYZ list and not a dict. |
| `capture_image(arm, capture_name)` | grab_object | Capture an image with the named arm's camera. |
| `compute_tcp_pose_from_tip_position(...)` | epipette_grey_aspirate | Compute the TCP pose given a desired pipette tip position. |
| `compute_dispense_orientation(...)` | epipette_grey_aspirate | Compute the wrist orientation for dispensing into a target. |
| `epipette_aspirate(volume, speed)` | epipette_grey_aspirate (as helper) | Aspirate a volume from the pipette. |
| `epipette_dispense(volume, speed)` | epipette_grey_dispense | Dispense a volume. |
| `epipette_home()` | epipette_grey_aspirate | Move the pipette to its home position. |
| `print_log(msg)` | most skills | Log a message visible in the execution UI. |

This list is **far from exhaustive**. The platform's execution-functions module likely exposes dozens more (perception, vision, world-state queries, simulation hooks, etc.).

---

## Cross-skill imports (super-skills)

A skill can call other skills in the same project:

```python
from sibling_skill.robotic_code import sibling_skill
```

This is verified to work — `skills/` is on `sys.path` at execution time. See `golden-gate-assembly-mp6n1k2x/skills/run_platefuge/robotic_code.py` and `mm_prep/robotic_code.py` for the pattern.

When authoring a "super skill" that composes others, prefer this pattern over re-implementing logic.

---

## Private helpers inside `robotic_code.py`

A skill can define private helpers (constants, math helpers) **inside its own `robotic_code.py`**, at module scope above the public function:

```python
from execution.skill_editing.execution_functions import *

# Module-level constants/helpers (private to this skill)
RIGHT_ARM_INNER_SWING_JOINT = [1.675, -0.730, -0.815, 0.043, 1.567, 4.833]

def _approach_pose(target):
    ...

def my_skill(...):
    ...
```

Anything above the public function is private to this skill. There is no separate `modules.py` to put them in.

---

## Red flags for the skill author

- The user asks for "rotate joint 6" / "move 1cm up" / etc. without naming a function. → ask whether such a function exists in their platform; if not, suggest scaffolding a stub with a TODO comment.
- The user references a function name not in this file and not in any existing skill in the project. → ask before writing it; offer to grep the codebase if you have access.
- A working skill in the project uses a function not listed here, **imported from `execution.skill_editing.execution_functions`**. → use it (the project is the ground truth, this file is incomplete) and consider adding it to this file.

## Local helpers ≠ execution functions

When you `grep` for a function name in `skills/*/robotic_code.py` and find a match, **check whether the match is an `import` of a real execution function or a `def` of a per-skill helper**. Local helpers (functions `def`-ed inside another skill's `robotic_code.py`, or module-level constants) are NOT available to other skills via `from execution.skill_editing.execution_functions import *`.

A local helper found via grep is **not** evidence that the function exists in the executor module. Don't import it cross-skill unless the user explicitly wants this composition pattern (see `examples/skill-super-calls-others.md` for the supported sibling-import form: `from <peer_skill>.robotic_code import <peer_skill>`, not deep-reaching into a sibling's helpers).
