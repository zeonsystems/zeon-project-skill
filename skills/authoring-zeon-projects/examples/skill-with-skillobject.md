# Example: skill with a `SkillObject` parameter

This is the real `wellplate_pcr_grab` skill from the `golden-gate-assembly` project. It takes a world object plus an optional anchor name; the function signature drives parameter inference automatically — `metadata.yaml` doesn't list `parameters` at all.

Source: `golden-gate-assembly-mp6n1k2x/skills/wellplate_pcr_grab/`.

## `skills/wellplate_pcr_grab/metadata.yaml`

```yaml
skill_id: wellplate_pcr_grab
version: "1.0.0"
description: "Right arm grabs a PCR wellplate using a specified anchor. Attaches plate to arm for world model tracking."

# parameters are derived from the wellplate_pcr_grab() signature in robotic_code.py

tags:
  - manipulation
  - wellplate_pcr
  - right_arm
```

No `parameters:` list; the loader's AST inference reads them from the function signature. No `preconditions`/`postconditions` here — they're optional, omit if not needed.

## `skills/wellplate_pcr_grab/robotic_code.py`

```python
import time

from execution.skill_editing.execution_functions import (
    anchor_preapproach,
    attach_object_to_arm,
    load_object_anchor,
    move_arm,
    move_arm_js,
    move_relative,
    set_gripper,
)
from protocol_schema import SkillObject

RIGHT_ARM_INNER_SWING_JOINT_180 = [1.675, -0.730, -0.815, 0.043, 1.567, 1.691]
RIGHT_ARM_INNER_SWING_JOINT = [1.675, -0.730, -0.815, 0.043, 1.567, 4.833]
RIGHT_ARM_PLATE_PICK = [0.797, -0.376, -1.065, 0.012, 1.472, 0.813]


def wellplate_pcr_grab(object: SkillObject, anchor: str = "grasp_short"):
    object_id = object.id

    move_arm_js(arm="right_arm", joint_angles=RIGHT_ARM_INNER_SWING_JOINT_180, safe=False, speed=0.2)
    move_arm_js(arm="right_arm", joint_angles=RIGHT_ARM_PLATE_PICK, safe=False, speed=0.2)
    set_gripper(arm="right_arm", width_m=0.10)
    pick = load_object_anchor(object_id, anchor)
    pick_xyz = pick["xyz"]
    preapproach = anchor_preapproach(pick, default_standoff=0.15)
    preapproach_high = [preapproach[0], preapproach[1], preapproach[2] + 0.05]

    move_arm(arm="right_arm", position=preapproach_high, orientation=pick["rpy"], safe=False, speed=30)
    move_arm(arm="right_arm", position=preapproach, orientation=pick["rpy"], safe=False, speed=30)
    move_arm(arm="right_arm", position=pick_xyz, orientation=pick["rpy"], safe=False, speed=30)
    move_relative(arm="right_arm", delta_xyz=[0, 0, -0.001], safe=False, speed=50)  # ZEON_OFFSET
    set_gripper(arm="right_arm", width_m=0.065)
    time.sleep(0.5)
    attach_object_to_arm(object_id, arm="right_arm")
    move_arm(arm="right_arm", position=preapproach, orientation=pick["rpy"], safe=False, speed=30)

    return {"success": True}
```

## What the loader infers from the signature

- `object`: type `object` (`SkillObject` → `ParameterType.OBJECT`), required (no default).
- `anchor`: type `string`, default `"grasp_short"`, required `false`.

Descriptions come from the docstring's `Args:` block (this example has none — fine for tags-only metadata; add a docstring when you want UI tooltips).

## Patterns to learn from

- **Selective imports** from `execution.skill_editing.execution_functions` (you can `import *` or list the names you use — both work).
- **Module-level constants** for joint configurations — keep them at module scope, not in the function.
- **`object.id`** is the world-object's instance ID; pass it to executor functions like `attach_object_to_arm` that need the id rather than the SkillObject wrapper.
- **`load_object_anchor(object_id, anchor)`** returns a pose dict with `xyz` and `rpy` keys — use those to feed `move_arm`.
- **`anchor_preapproach(...)`** computes a safe approach pose at a standoff distance above the anchor.
- **`move_relative(...)`** for small deliberate offsets the arm should apply in its current frame.
- **Return shape**: a dict, conventionally `{"success": True}` on success.
