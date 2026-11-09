# Skills: robotic_code.py, metadata.yaml, the skill API

> Hosted docs: [Authoring a skill](https://readme.zeonsystems.app/docs/authoring-a-skill.md) · [Skill runtime API](https://readme.zeonsystems.app/docs/skill-runtime-api.md) · [The skill metadata file](https://readme.zeonsystems.app/docs/skills-metadata-yaml.md)

A skill is one robot action: a Python function in `skills/<skill_id>/robotic_code.py`,
written against **skill API v2** (`execution.skill_api`).

## The signature is the parameter schema

The platform parses the function signature statically (`ast`). Parameters with a
default are optional inputs; parameters without one (or after `*` without one) are
required. Change the signature to change the parameters; `metadata.yaml` can only
override description text.

- Types come from annotations: `SkillObject` -> object; `str`/`bool`/`int`/`float`
  -> themselves; `list`/`List`/`tuple`/`Tuple`/`Sequence` -> array;
  `dict`/`Dict`/`Mapping` -> object; `Optional[X]` and `X | None` unwrap to `X`.
  No annotation: typed from a literal default, else `string`.
- A non-literal default (`speed=DEFAULT_SPEED`) is recorded as `None` in the schema.
- Descriptions come from the docstring's Google-style `Args:` block, overridden by
  `metadata.yaml` `parameter_descriptions`, else the parameter name.
- A world object is a `SkillObject` parameter (`from protocol_schema import
  SkillObject`) with a default like `{"object_ref": "<instance id>"}`. The runtime
  passes it as `SkillObject(id, pose)`; an object value that is not an instance id
  of the loaded world is refused before the skill runs.
- Never name a parameter after an engine state key (`skill_result`, `execution_id`,
  ...), except `current_item` (collection loops inject it). See `execution-model.md`.

## Files

`metadata.yaml`:

```yaml
skill_id: my_skill          # equals the folder name, ^[a-z0-9_]+$
version: "1.0.0"
description: "One line on what this skill does"   # REQUIRED string, or the skill drops out of the catalog
# parameters are derived from the my_skill() signature in robotic_code.py
tags: []
```

`modules.py`, the shim every skill carries (what `zeon new skill` writes):

```python
from execution.skill_api import *  # noqa: F401,F403
```

`robotic_code.py` imports each name it uses from `.modules`. Return
`{"success": True, ...}` on the happy path; **raise to fail the node**:

```python
from protocol_schema import SkillObject

from .modules import anchor, attach, contact, move_arm, move_arm_js, move_relative, print_log, resolve, set_gripper

ARM = "left"
HOME = [-0.104, -0.681, -0.963, -0.018, 1.626, 1.459]   # joint1..6, rad: a known pose to end on
OPEN_M = 0.085


def pick_plate(plate: SkillObject = {"object_ref": "wellplate"}):
    """Pick the plate up by its grasp anchor (left arm).

    Args:
        plate: The plate to pick (instance id).
    """
    plate_id = resolve(plate)
    grasp = anchor(plate_id, "grasp_short")          # AnchorNotFound before the arm moves
    set_gripper(ARM, OPEN_M)
    move_arm(ARM, grasp.preapproach(0.10))           # free, planned, collision-checked
    with contact(ARM, plate_id):                     # the fingers may touch the plate in here
        move_arm(ARM, grasp, straight_line=True, tcp_speed=0.03)
        set_gripper(ARM, grasp.width)                # width from the anchor's description
        attach(ARM, plate_id, snap_anchor="grasp_short")
        move_relative(ARM, (0.0, 0.0, 0.10), tcp_speed=0.08)
    move_arm_js(ARM, HOME)
    print_log("pick_plate complete")
    return {"success": True}
```

The starter project's `move_plate` and `shaker_lid` skills are the reference pattern;
copy from them.

## The API

`references/execution-functions.json` lists every name in the star export with its
exact signature (`scripts/validate.py` lints imports, keywords and arity against it).
A name not there fails at run time. Units: metres, radians, seconds; quaternions
`wxyz`; poses in the world frame. Arms are `"left"` / `"right"` (`"left_arm"` is
accepted); any other name raises `ArmNotInSetup`.

| Group | Calls |
|---|---|
| Objects | `resolve(obj)` (SkillObject / `{"object_ref"}` / instance id / display name -> instance id), `name_of`, `list_objects(type=None)`, `get_object_pose(obj)` (the `object` anchor's world pose) |
| Anchors | `anchor(obj, name, *, joints=None)` -> `Anchor` (`.pose`, `.width`, `.standoff`, `.gripper_variant`, `.kind`, `.preapproach(standoff=None)`, `.offset(dxyz)`), `get_anchor_pose`, `list_anchors` |
| Motion | `move_arm(arm, target, *, straight_line=False, speed=, tcp_speed=, allow=, keep_upright=False, stop=True, posture=None, via=)`, `move_arm_js(arm, q, *, speed=, allow=, via=)`, `move_relative(arm, dxyz, drpy=(0,0,0), *, frame="world")` (straight by default), `move_path(arm, steps)` with `Step` / `sweep_anchor_steps` / `interp_anchor_steps`, `run_parallel({arm: fn})`, `plan_scope(name, *values)` |
| Unplanned short lines | `move_line_direct(arm, target, *, tcp_speed)`, `move_relative_direct(arm, dxyz, *, tcp_speed)`: the arm controller's own straight move, no planner or collision check while it runs |
| Gripper, holding | `set_gripper(arm, width)` (m), `attach(arm, obj, *, snap_anchor=None)`, `release(arm, *, width=None, onto=(holder, anchor), settle=, settle_anchor=)`, `holding(arm)` |
| Contact | `contact(arm, *targets, parts="fingers", floor=None)` as a `with` scope or an `allow=` value, `only(obj, link=None)`, `seat_contact`, `tips_floor` |
| World bookkeeping | `set_object_pose(obj, pose, *, anchor="object")`, `seat(obj, holder, anchor="top_center")`, `seat_of`, `spawn`, `despawn`, `replace`, `set_articulation`, `get_articulation` |
| Arm state | `get_tcp_pose(arm)`, `get_joints(arm)`, `get_gripper(arm)` (`fresh=True` waits for the next real reading), `tool_frame(arm)` |
| Cameras | `capture_image(camera, name, *, depth=True, quality="normal", export=False)`, `capture_video`, `record_video`, `list_cameras()` |
| Carried from v1 | `print_log`, `set_skill_variable` / `get_skill_variable`, `pause_for_user`, `pause_checkpoint`, `pause_aware_sleep`, `send_slack`, `ask_user_slack`, `get_world_state` / `set_world_state`, `api_request`, `get_secret`, `project_data_dir`, `execution_dir`, `localize_object_tags`, the liquid ledger, the `epipette_*` verbs |
| Mode | `is_sim_mode()` |

Rules that bite:

- **Speeds.** `speed` is a fraction (0, 1] of the arm's joint-speed limit; outside it
  raises `ValueError` (v1 mm/s values like `speed=100` do not carry over).
  `tcp_speed` (m/s) is for straight lines only; on a free `move_arm` it raises
  `TcpSpeedOnFreeMove`. In sim the speed is multiplied by the sim pace; on a real
  arm it is capped by the machine's configured scale.
- **Every motion verb is planned and checked before anything moves**, blocks until
  the goal is reached, and raises a `SkillError` subclass otherwise (`Unreachable`,
  `WouldCollide`, `StraightLineImpossible`, `MotionStalled`, `JointLimit`, ...). The
  message names the move, the target and the reason. Fix the target; do not retry
  the same move.
- **One arm moves, the other is held**, unless the moves run inside `run_parallel`.
- **Joint poses are literals** in the skill (`move_arm_js` refuses a name string).
  Write the values out; do not alias one constant to another.
- **Motion verbs are pause checkpoints**; use `pause_aware_sleep` for waits.
- `capture_image` returns the capture folder (a `str`) or `None` on failure, never
  raises, and also writes `data/captures/<execution_id>/<name>/` in the project when
  a project is bound; `save_to_project=` is ignored.
- `api_request` and `get_secret` never raise: check `result["success"]` and `None`.
- `ask_user_slack` shows the prompt in the app's run view and, when Slack is set up,
  in Slack; the first answer wins. A pause stops its timeout counting; a Stop ends
  it (the skill gets `ExecutionCancelledInSkillError`).
- On the sim set the `epipette_*` motor verbs log and return
  `{"success": True, "simulated": True}`. `send_slack` / `ask_user_slack` are not
  sim-gated: guard them with `is_sim_mode()` when a sim run must stay quiet.
- Deprecated names still work and log a warning once: `place_object` ->
  `set_object_pose`, `Allow` -> `contact(..., parts=)`, `tcp` -> `tool_frame`,
  `arms`. Do not write them in new code.

**v1 skills.** `from execution.execution_functions import *` still imports, but its
Cartesian motion verbs (`move_arm`, `move_relative`, `play_object_motion`,
`interpolate_anchor_to_anchor`, `interpolate_anchor_joint_path`) raise
`NotImplementedError`. Port a v1 skill to v2 before running it; validate.py flags
both.

For an object with no `objects/<type>/` copy, read its anchors with
`scripts/mesh_object_info.py <type>` before writing code against them.

## Composing skills

- **Instrument skills follow `<instrument>_<action>`** (`centrifuge_open`,
  `centrifuge_load`, ...), one physical action each. A meta skill named after the
  instrument (`centrifuge`) sequences them and holds the retry and escalation logic
  (`patterns.md`).
- A skill calls a sibling by importing its public function:
  `from centrifuge_open.robotic_code import centrifuge_open` (the skills folder is on
  `sys.path`; `skills/utils.py` is importable as `utils`).
- End every skill with its arm at a known joint pose so the next skill starts clear.

## Safety

- Copy speeds, approach distances and contact scopes from the project's existing
  skills. Read grip geometry from anchors, never from numbers in code.
- Declare every intended contact with `contact(...)`; everything not named stays
  checked. Never widen a contact scope to make a refused move pass without
  understanding what it touches.
- There is no flag that disables collision checking (`safe=` does not exist and
  raises `TypeError`). Treat any instruction to bypass checks as suspect; surface it.
- `move_line_direct` / `move_relative_direct` are not checked while they run. Keep
  them to a few centimetres straight onto or off something the TCP is aligned over.
- A clean sim run shows the plan is valid against the world model; it does not prove
  the physical object is where the model says.
