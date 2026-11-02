# Motion-skill patterns — how good Zeon skills are written

> Hosted docs: [Skill authoring patterns](https://readme.zeonsystems.app/docs/skill-authoring-patterns.md) · [Arm motion and the gripper](https://readme.zeonsystems.app/docs/arm-motion-and-the-gripper.md) · [How anchor snapping works](https://readme.zeonsystems.app/docs/anchor-snapping.md)

Idioms distilled from the platform's own projects, in the skill API v2
(`references/skills.md`). These are what separate a
skill that survives on hardware from one that only looks right.

## Anchor-driven geometry — never bake numbers

All geometry comes from anchors. `anchor(obj, name)` returns an `Anchor`
evaluated in the world now: its `.pose`, and the grasp its object model
declares — `.width`, `.standoff`, `.gripper_variant`. Read them, don't
hardcode:

```python
g = anchor(plate, "grasp_shortside")      # Anchor: .pose, .width, .standoff, .gripper_variant
set_gripper(ARM, g.width + 0.02)          # open past the grasp width
move_arm(ARM, g.preapproach())            # the anchor's standoff, else 0.05 m, back along its -z
move_arm(ARM, g, straight_line=True, tcp_speed=0.02)
set_gripper(ARM, g.width)                 # from the anchor, not a constant
```

`preapproach(standoff=None)` uses the anchor's declared standoff, else
**0.05 m**; pass `standoff=` only to deliberately override. `width` is `None`
when the anchor states no grasp — fall back to an explicit value then, but say
so. Hardcoded widths are what make a skill work for exactly one piece of
labware; when geometry is wrong, the fix is usually **re-teach the anchor**, not
edit the code. A missing target is an anchor to add on the holder's object
model (`references/worlds-and-objects.md`).

`anchor(obj, name, joints={"lid_joint": 1.2})` evaluates the anchor at
hypothetical joints of an articulated object (a lid handle where the lid will
be). `.offset(dxyz, frame="local")` moves it along its own axes.

**Placing held labware means seating it**: the held object's `bottom_center`
anchor goes onto the holder's seat anchor. The TCP target is the seat composed
with the held object's `bottom_center`-to-grasp transform, recomputed from the
world on every move, so it follows the holder wherever localization puts it and
works for any labware height and grab. Look for such a helper in the project
(`skills/*.py`) before writing one.

## The approach shape: preapproach, then a straight descent

Approach from a standoff with a planned free move, then go straight in slowly:
a free `move_arm` (or a taught `move_arm_js` waiting pose) to the preapproach,
then `straight_line=True` legs at a low `tcp_speed` (typically 0.01-0.03 m/s)
inside a `contact` scope for the descent, the grasp and the lift. Lift straight
up (`move_relative(arm, (0, 0, dz))`) before any lateral move.

**Start and end at a transition pose.** Relocating an arm across the
workspace (between instruments) goes through named joint poses as
`move_arm_js` waypoints (taught configurations — no IK branch to flip), then
the anchor-driven approach. Skills that begin and end at a known pose compose
with any other skill — the modularity contract that makes meta-skills pure
sequencing. See `references/transition-poses.md`.

**Posture.** When a free move to a pose can resolve on more than one arm
configuration and the wrong one matters (a wrist that flips, an elbow that
swings through an instrument), pass the project's `posture=` constant
(`references/skills.md`).

## `move_relative`: world axes by default, tool axes on request

`move_relative(arm, dxyz)` moves along the **world** axes (`frame="world"`,
the default) — what you want for a lift (`(0, 0, 0.03)`). `frame="tool"` moves
along the TCP's own axes — a push along the approach direction. For an
object-aligned slide, take the direction from the object's anchors
(`a.offset((0, 0, 0.01))` is 1 cm along the anchor's z) and target that pose.

## Contact: permit exactly what touches

The planner keeps every part of the arm, the gripper and the held object clear
of everything by default. Touching is permitted only through `contact(...)`,
as a `with` scope (every move of that arm inside) or one move's `allow=`:

```python
with contact(ARM, plate):                                       # fingers vs the plate (and what it sits on)
    move_arm(ARM, g, straight_line=True, tcp_speed=0.02)
move_arm(ARM, p, straight_line=True, allow=contact(ARM, rack, parts="held", floor=0.002))
```

`parts` picks which parts of the arm may come close: `"fingers"` (default),
`"palm"`, `"gripper"`, `"held"`, `"arm"`, `"side"`, or a part name; `floor=` is
how close (m) they still must stay. `only(obj)` / `only(obj, link)` limits a
target to that object (or one link of it) alone. Keep scopes short and targets
narrow; a refusal is usually a wrong target or approach, not a missing
allowance.

## Attach / release: the world is bookkeeping you keep

Closing the gripper does not make the arm hold anything in the model. The
booking is what keeps collision checking and the next skill's planning right:

- **On pick**, right after the gripper closes: `attach(arm, obj,
  snap_anchor="grasp")` — the grasp anchor booked exactly at the TCP (the
  canonical grip). Without `snap_anchor` the object is booked where it hangs
  relative to the TCP now.
- **On place**: `release(arm, onto=(holder, "slot_5"))` opens the gripper and
  books the object seated on the holder's anchor; add `settle=<Anchor|Pose>`
  (and `settle_anchor=`) to book where it comes to rest.
- `set_object_pose(obj, pose)` books an object somewhere without motion (a
  perception correction, a person moved it); `seat(obj, holder, anchor)` books
  a seating a person did.
- Booking **asserts, it does not measure** — sim stays deterministic, but a
  marginal real grasp still books clean. A green sim run is therefore not
  evidence a grasp is safe; say so when relevant. Projects that need it compare
  the booked pose against a fresh arm reading after the grasp.

## Articulated objects (lids, drawers, doors)

For a lid whose handle anchor travels with the articulation, follow the arc as
one path; the World takes the final joint angle when the arm reaches it:

```python
move_path(ARM, sweep_anchor_steps(shaker, "lid_handle", "lid_joint", 0.0, 1.3, 13, 0.05))
```

`interp_anchor_steps(obj, a0, a1, joints, steps, tcp_speed)` moves between two
anchors of the object as straight steps (a re-grip). Changing an articulation
without motion is `set_articulation(obj, "open")` (a preset) or
`set_articulation(obj, {"lid_joint": 1.3})`; a skill that moves a lid any other
way must book the new angle, or the next skill plans around a lid it believes
is closed.

## shared_state: cross-skill handoff for pick/place pairs

`from execution.skill_editing import shared_state` is a mutable namespace
that is **not cleared between runs**. `set_skill_variable` storage is only
a little safer: it is cleared when a **workflow run or a CLI run starts, and
at no other time** — nothing clears it when a run *ends*, and a Sim run from
the Skills Editor doesn't clear it at all, so it begins with whatever the
previous run left behind. Treat both as potentially stale: overwrite stashes
at the start of the producing skill and treat a guard hit as possibly left
over from a previous run.
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
- **Slack helpers post real messages from sim runs** on a machine with Slack
  credentials in Secrets. Guard `send_slack`/`ask_user_slack` too.
- In sim, return fabricated sensor data shaped exactly like the real result,
  chosen so downstream checks pass (e.g. `laser_read` reports tip-present).
- Pace sim with `pause_aware_sleep(...)` (respects pause/stop), not bare
  `time.sleep` for long waits.

## Credentials: Secrets, never code

- Never hardcode a token, and never pass one as a workflow input. The user
  stores it in the machine's Secrets (header ⋮ menu → **Secrets**,
  UPPER_SNAKE_CASE names); the skill names it:
  `api_request(url, auth_secret="NAME")` for a bearer token, `get_secret("NAME")`
  for anything else.
- Secret values are not masked anywhere. Never `print_log`, `send_slack`, save,
  or return one, and never put one in a URL (URLs are logged and saved).
- `api_request` never raises, including for a missing secret. Check
  `result["success"]` and raise when the node should fail:

```python
result = api_request(url, method="POST", json_body=body, auth_secret="INSTRUMENT_API_TOKEN")
if not result["success"]:
    raise RuntimeError(f"API call failed: {result['error']}")
```

- Secrets exist only on a local install. In the cloud, `get_secret` returns the
  default and an `auth_secret` call is skipped, so the same skill runs in both.

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

Catch specific errors, never bare `except`: a planner refusal
(`WouldCollide`, `Unreachable`, ...) is raised before anything moved and will
refuse again with the same inputs; retrying it is pointless. Real-hardware
failures (`GraspFailed`, `ContactDetected`) are what a retry is for.

## SkillObject: the 12-float pose

A `SkillObject` has `.id` (world instance id) and `.pose`, a 12-float list:

```
[centroid_x, centroid_y, centroid_z,  roll, pitch, yaw,
 extent_x, extent_y, extent_z,  origin_x, origin_y, origin_z]
```

`origin_*` and `roll/pitch/yaw` are the world pose of the object's **`object`
anchor** (the object frame), not of its mesh or URDF origin. `centroid_*` is the
mesh centroid in world, and `extent_*` the mesh bounding-box size. The object
frame, the mesh centroid and the mesh origin generally differ on real objects. Indexing `pose[0:3]` when you meant the
object frame moves the arm by the centroid offset — sim may tolerate it;
hardware won't. Prefer anchors over raw pose math (`references/worlds-and-objects.md`,
"The object frame is the `object` anchor").

## Shared code: skills/*.py, not modules.py

`modules.py` stays the one-line API import. Code several skills share —
the project's motion helpers, constants, joint poses, rules — lives in modules
next to the skill folders (`skills/utils.py`, `skills/cell.py`, ...) and is
imported by name (`from cell import move`); the loader puts `skills/` on
`sys.path`. Names starting with `_` are a module's internals. Keep
`robotic_code.py` to the skill function and its signature (the platform's AST
parse reads it). Import a sibling's *public* skill function via
`from <sibling>.robotic_code import <sibling>`.
