# Example: skill with a `SkillObject` parameter

A skill that accepts a world object plus an anchor name. The function signature drives parameter inference automatically — `metadata.yaml` can omit `parameters` entirely.

## `skills/move_to_anchor/metadata.yaml`

```yaml
skill_id: move_to_anchor
version: "1.0.0"
description: "Move the gripper to a named anchor on an object."

preconditions:
  arm_homed: true
  object_visible: true

postconditions:
  gripper_at_anchor: true

tags:
  - manipulation
  - navigation
```

## `skills/move_to_anchor/robotic_code.py`

```python
from .modules import *
from protocol_schema import SkillObject


def move_to_anchor(target: SkillObject, anchor: str = "object", speed: float = 100.0):
    """Move the gripper to a named anchor on `target`.

    Args:
        target: World object to approach.
        anchor: Name of an anchor declared in target's object_model.yaml.
            Defaults to the always-present "object" anchor.
        speed: Joint speed for the motion.
    """
    pose = load_object_anchor(target, anchor)
    move_arm(arm="left_arm", position=pose[:3], orientation=pose[3:6], speed=speed)
    return {"success": True}
```

## `skills/move_to_anchor/modules.py`

```python
from execution.skill_editing.execution_functions import *
```

## What the loader infers

From the function signature it derives `parameters`:

- `target`: type `object` (SkillObject → ParameterType.OBJECT), required.
- `anchor`: type `string`, default `"object"`, required `false`.
- `speed`: type `float`, default `100.0`, required `false`.

Descriptions are pulled from the docstring's `Args:` block.

## Why this works

- `SkillObject` is the canonical type for world-object parameters.
- `load_object_anchor` resolves the anchor (declared in `objects/<type>/<type>.object_model.yaml`) into a 6-DOF pose.
- `move_arm` is a real execution-function (confirmed in golden-gate skills).
- Default `anchor="object"` works because every object_model.yaml declares an `object` anchor.
