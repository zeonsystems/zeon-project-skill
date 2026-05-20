# Example: super-skill that composes other skills

A skill that orchestrates a sequence by calling sibling skills. The composing skill is no different structurally — it just imports peers and calls them.

## `skills/pick_and_place/metadata.yaml`

```yaml
skill_id: pick_and_place
version: "1.0.0"
description: "Pick up an object and place it at a destination."

tags:
  - composite
  - manipulation
```

## `skills/pick_and_place/robotic_code.py`

```python
from .modules import *
from protocol_schema import SkillObject

from grab_object.robotic_code import grab_object
from drop_object.robotic_code import drop_object


def pick_and_place(item: SkillObject, destination: SkillObject):
    """Pick up `item` and drop it onto `destination`.

    Args:
        item: Object to pick.
        destination: Where to drop it.
    """
    grab_object(object=item)
    drop_object(object=item, destination=destination)
    return {"success": True}
```

## `skills/pick_and_place/modules.py`

```python
from execution.skill_editing.execution_functions import *
```

## How this resolves at runtime

- `skills/` is on `sys.path` at execution time (see `services/execution/src/execution/project.py`).
- `from grab_object.robotic_code import grab_object` therefore resolves to `<project>/skills/grab_object/robotic_code.py`.
- Both sibling skills are independently executable; the super-skill just calls them as Python functions.

## Things to check

- Each peer skill (`grab_object`, `drop_object`) must exist at `skills/<id>/` in the same project.
- The peers' function names follow `_py_identifier(skill_id)` (dashes → underscores).
- If any peer changes its signature, this super-skill must update — there's no static check.

## When this is the right pattern

- A workflow's set of nodes is always called in the same order with the same parameters: collapse into a super-skill so the workflow can be a single node.
- You want to write tests against the composed behaviour as a unit.

## When NOT to compose

- The order of calls depends on inputs or conditions: use a `workflow` with multiple nodes and conditional edges instead. Skills should not embed graph-flow logic.
