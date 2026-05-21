# Example: super-skill that composes other skills

This is the real `run_platefuge` skill from the `golden-gate-assembly` project. It orchestrates a sequence by calling six sibling skills as plain Python functions. The composing skill is no different structurally from a leaf skill — it just imports peers and calls them.

Source: `golden-gate-assembly-mp6n1k2x/skills/run_platefuge/`.

## `skills/run_platefuge/metadata.yaml`

```yaml
skill_id: run_platefuge
version: "1.0.0"
description: "Super skill: open lid → pick plate → load into rotor slot → close → spin (wait) → open → unload → place plate on stand → close."

# parameters are derived from the run_platefuge() signature in robotic_code.py

preconditions:
  platefuge_visible: true
  arm_ready: true
  plate_on_stand: true

postconditions:
  plate_on_stand: true
  platefuge_closed: true

tags:
  - platefuge
  - centrifuge
  - wellplate-handling
```

## `skills/run_platefuge/robotic_code.py`

```python
import time

from platefuge_close.robotic_code import platefuge_close
from platefuge_load.robotic_code import platefuge_load
from platefuge_open.robotic_code import platefuge_open
from platefuge_unload.robotic_code import platefuge_unload
from platefuge_wellplate_pcr_pick.robotic_code import platefuge_wellplate_pcr_pick
from platefuge_wellplate_pcr_place.robotic_code import platefuge_wellplate_pcr_place

from protocol_schema import SkillObject


def run_platefuge(
    object: SkillObject,
    wellplate_stand: SkillObject,
    slot_index: int = 1,
    spin_duration: float = 300,
):
    """Super skill: open platefuge → pick plate → load into rotor → close →
    spin (wait) → open → unload from rotor → place plate back on stand → close.

    Args:
        object: The wellplate to spin.
        slot_index: Platefuge rotor slot to use (always 1 for GG assembly).
        spin_duration: Spin wait time in seconds.
    """
    object_id = object.id
    platefuge_open()
    platefuge_wellplate_pcr_pick(object_id=object_id)
    platefuge_load(slot_index=slot_index, object_id=object_id)
    platefuge_close()

    time.sleep(spin_duration)

    platefuge_open()
    platefuge_unload(slot_index=slot_index)
    platefuge_wellplate_pcr_place(object_id=object_id, wellplate_stand=wellplate_stand)
    platefuge_close()

    return {"success": True}
```

## How this resolves at runtime

- `skills/` is on `sys.path` at execution time (set up by `services/execution/src/execution/project.py`).
- `from platefuge_open.robotic_code import platefuge_open` therefore resolves to `<project>/skills/platefuge_open/robotic_code.py`.
- Each sibling skill is independently executable; the super-skill calls them as Python functions, passing through the relevant IDs.

## Patterns to learn from

- **Import the peer's function** by name from its `robotic_code` module — never `from .modules import ...` (no such file any more) and never deep-reach into helpers.
- **Param names match** between the super-skill signature and the peers' signatures where the data flows through (e.g. `object_id` is passed to several peers).
- **Defaults belong in the super-skill** — peers can have their own defaults too, but the super-skill exposes the high-level knobs (`slot_index`, `spin_duration`).
- **No motion logic inline** — the super-skill is pure orchestration. All the motion lives in the peer skills.
- **Docstring `Args:`** drives parameter descriptions in the UI. `slot_index` and `spin_duration` get descriptions; `wellplate_stand` doesn't (an oversight in this real example, worth filling in).
- **`time.sleep` is permitted** in skills — used here for the spin duration.

## When this is the right pattern

- A workflow's set of nodes is always called in the same order with the same parameters → collapse into a super-skill so a workflow node represents the whole sequence.
- You want to write a single test against the composed behaviour.
- The sequence is platform-tightly-coupled (specific device, specific protocol) and doesn't need user-facing branching.

## When NOT to compose

- The order of calls depends on inputs or runtime conditions → use a **workflow** with multiple nodes (and `conditional` / `loop` nodes if needed) instead. Skills shouldn't embed graph-flow logic.
