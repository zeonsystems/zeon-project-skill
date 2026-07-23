# Motion-skill patterns — how good Zeon skills are written

Idioms distilled from the platform's own projects. These are what separate a
skill that survives on hardware from one that only looks right.

## Anchor-driven geometry — never bake numbers

All geometry comes from anchors. Grip widths and standoffs ride on the anchor's
**grasp block** — read them, don't hardcode:

```python
grasp = load_object_anchor(plate.id, "grasp_shortside")
# grasp: {xyz, rpy, wxyz, standoff, width, gripper_variant, object_id}
pre = anchor_preapproach(grasp, default_standoff=0.10)   # world-xyz standoff point
move_arm(arm="left_arm", position=pre, orientation=grasp["rpy"], speed=100)
move_arm(arm="left_arm", position=grasp["xyz"], orientation=grasp["rpy"], speed=30)
set_gripper(arm="left_arm", width_m=grasp["width"])       # from the anchor, not a constant
```

When no grasp block exists, `standoff`/`width` come back `0.0` — fall back to
an explicit value then, but say so. Hardcoded widths are what make a skill work
for exactly one piece of labware; when geometry is wrong, the fix is usually
**re-teach the anchor**, not edit the code.

`load_object_anchor` also takes `joint_config={joint: angle}` (resolve an
anchor on an articulated object at a chosen angle) and `index=` (indexed
anchors like well positions).

## The approach shape: preapproach, then a speed ladder

Approach from a standoff and descend at decreasing speeds — fast in free space,
slow near contact (typical ladders: 100→60→10, or 70→40→10; joint-space moves
use fractional speeds ~0.5). Lift straight up (world +Z) before any lateral
move. Small `time.sleep(0.1–0.5)` settles between gripper actions.

**Start and end at a transition pose.** Relocating an arm across the
workspace (between instruments/azimuths) is never a free-space Cartesian
move: route through the named transition poses as `move_arm_js` waypoints
(no IK solve — can't fail or elbow-flip), then finish with the anchor-driven
approach. Skills that begin and end at a transition pose compose with any
other skill without pairwise path planning — this is the modularity contract
that makes meta-skills pure sequencing. See `references/transition-poses.md`.

## `move_relative` deltas are WORLD-frame

`move_relative` adds `delta_xyz` in the **world frame**, regardless of how the
tool or object is oriented. For an object-aligned slide, derive the direction
from the object's own anchors:

```python
grasp = load_object_anchor(obj.id, "grasp")
pre = anchor_preapproach(grasp, default_standoff=0.06)
d = [g - p for g, p in zip(grasp["xyz"], pre)]           # unit direction × distance
move_relative(arm="left_arm", delta_xyz=[x * 0.5 for x in d], speed=20)
```

Deliberate world-frame lifts (`delta_xyz=[0, 0, 0.1]`) are fine — that's the
one case where world-frame is what you mean.

## Attach / snap / detach discipline

Attach state is what keeps collision tracking and sim determinism correct.

- **On pick**, right after the gripper closes: assert the canonical grip —
  snap the object's grasp anchor onto the live TCP, then attach.
  `get_arm_pose` returns a flat 6-float array (`[x, y, z, roll, pitch, yaw]`),
  so convert the rpy half to a wxyz quaternion first:
  ```python
  import numpy as np
  from common_models.transform import rpy_to_quat_wxyz

  tcp = get_arm_pose("left_arm")                       # numpy [x,y,z,roll,pitch,yaw]
  snap_object_anchor_to_world_pose(obj.id, "grasp",
                                   [float(v) for v in tcp[:3]],
                                   rpy_to_quat_wxyz(np.asarray(tcp[3:])).tolist())
  attach_object_to_arm(obj.id, "left_arm")
  ```
- **On place**: release the gripper, `detach_object_from_arm(obj.id)`, then
  snap the object to its seated pose (`snap_object_anchor_to_world_pose` onto
  the fixture's seat anchor).
- Snapping **asserts, it does not measure** — sim stays deterministic, but a
  marginal real grasp still snaps clean. A green sim run is therefore not
  evidence a grasp is safe; say so when relevant.
- A snap **pins to a world pose — it does not parent**. An object seated in a
  fixture does not follow the fixture: if the fixture moves, re-snap the
  object. Fixtures often carry paired anchors (a *load* pose and a *settled*
  pose): release at the load anchor, snap to the settled anchor, and target
  the settled one for later picks.

## Articulated objects (lids, drawers): resolve → sweep → commit

For a lid/lever whose grasp anchor travels with the articulation, use
`interpolate_anchor_joint_path` — it re-resolves the anchor at every step and
**commits the joint change to the world model for you** (`sync_joint_config=True`
by default):

```python
interpolate_anchor_joint_path(arm="left_arm", object_name=obj.id,
                              anchor_name="lid_handle",
                              joint_path={"lid_joint": (0.0, 1.4)}, steps=12)
```

The lower-level `interpolate_anchor_to_anchor(arm, object_name, start_anchor,
end_anchor, *, start_joint_config=None, end_joint_config=None,
interpolate=False, steps=5)` does **not** commit — follow it with
`update_object_joint_config(obj.id, {"lid_joint": 1.4})`, and note `steps` only
applies with `interpolate=True` (the default is two discrete moves). A missed
commit is an invisible bug: this skill passes, and the *next* skill's planner
collides with a lid it believes is closed. Exact signatures: the manifest,
`references/execution-functions.json`.

## shared_state: cross-skill handoff for pick/place pairs

`from execution.skill_editing import shared_state` is a mutable namespace
that is **not cleared between runs** (unlike `set_skill_variable` storage,
which resets at each execution start). Overwrite stashes at the start of the
producing skill and treat a guard hit as possibly stale from a previous run.
Conventions:

- Prefix attributes with the producing skill: `epipette_grab_home_pose`,
  `wellplate_grab_grasp`.
- The **pick** skill captures poses *while the object is still seated* (before
  lifting) and stashes them; the **place** skill replays the stash instead of
  re-resolving anchors. Re-resolving a grasp anchor after pickup returns the
  *elevated* pose — driving the arm to it on place is a crash. The platform's
  own place skills work this way; copy it.
- Guard reads: `getattr(shared_state, "x", None)` with a clear raise when the
  pick skill hasn't run.

## live_state.yaml: consumables and calibration

The full contract lives in `references/live-state.md` — read it before writing
any skill that touches tips, wells, or calibration. The three rules that cause
silent physical errors when violated: **tip indexing is 1-based** (`"1".."96"`,
advance and stop at 96 — never `% 96`), **wells are keyed by label**
(`"A1".."H12"`, identical to anchor names), and **`get_world_state`/
`set_world_state` key by `SkillObject.id`** — a display name silently returns
`{}` and zeros out your calibration. Read idiom:
`dx, dy = get_world_state(obj.id).get("calibration", {}).get(str(key), [0.0, 0.0])`.

## Sim honesty — what is and isn't simulated

- Gate hardware-only side effects: `if not is_sim_mode():` around device
  HTTP/BLE/zigbee calls. **Pipette verbs are not sim-abstracted** — in sim
  they still attempt a real Bluetooth connection and can hang for minutes.
- **Slack helpers post real messages from sim runs.** Guard
  `send_slack`/`ask_user_slack` too.
- In sim, return fabricated sensor data shaped exactly like the real result,
  chosen so downstream checks pass (e.g. `laser_read` reports tip-present).
- Pace sim with `pause_aware_sleep(...)` (respects pause/stop), not bare
  `time.sleep` for long waits.

## Reliability: attempt → verify → retry → escalate

This shape lives in **meta skills** — the `<instrument>` skill that sequences
the `<instrument>_<action>` atomics (naming contract: `references/skills.md`).
The platform's robust skills wrap flaky physical steps like this:

```python
def tip_attach_robust(...):
    for attempt in range(2):
        _attempt_attach(...)
        if _tip_present():          # a sensor skill, not hope
            return {"success": True}
        _cleanup_partial(...)       # undo before retrying
    pause_for_user("Tip attach failed twice — fix the tip box and resume.")
    ...
```

Escalation ladder, in order: `print_log` (always) → `send_slack` (notify) →
`ask_user_slack` (question, keeps running) → `pause_for_user` (blocks the run
until the operator resumes; supports `on_resume` callbacks). Retry without a
verify step and cleanup is not a retry — it's the same failure twice.

## SkillObject: the 12-float pose

A `SkillObject` has `.id` (world instance id) and `.pose`, a 12-float list:

```
[centroid_x, centroid_y, centroid_z,  roll, pitch, yaw,
 extent_x, extent_y, extent_z,  origin_x, origin_y, origin_z]
```

Centroid (mesh center, world frame) ≠ origin (object-frame origin). Indexing
`pose[0:3]` when you meant the origin moves the arm by the centroid offset —
sim may tolerate it; hardware won't. Prefer anchors over raw pose math.

## modules.py layering

The one-line star shim is the base case, but `modules.py` is also the
sanctioned home for skill-local geometry/math helpers layered on top of the
platform import (pose math, TCP offset transforms) — keeping `robotic_code.py`
signature-clean for the platform's AST parse. Sibling skills may chain-shim
(`from <sibling>.modules import *`) to share helpers; import a sibling's
*public* skill function via `from <sibling>.robotic_code import <sibling>`.
