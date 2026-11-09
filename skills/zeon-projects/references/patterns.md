# Motion-skill patterns: how good Zeon skills are written

> Hosted docs: [Skill authoring patterns](https://readme.zeonsystems.app/docs/skill-authoring-patterns.md) · [Arm motion and the gripper](https://readme.zeonsystems.app/docs/arm-motion-and-the-gripper.md) · [How anchor snapping works](https://readme.zeonsystems.app/docs/anchor-snapping.md)

Skill API v2 idioms, as the starter project's `move_plate` and `shaker_lid` use them.

## Geometry comes from anchors

```python
grasp = anchor(plate_id, "grasp_short")   # Anchor: .pose (world), .width, .standoff, .gripper_variant
pre = grasp.preapproach()                  # standoff back along the anchor's -z
```

- An anchor's grasp lives in its **description**:
  `"Grip the short side | grasp: width 0.075 m, standoff 0.04 m, gripper_variant wellplate"`.
  `anchor()` parses it into `.width` / `.standoff` / `.gripper_variant` (`kind == "tcp"`).
  Without a grasp segment `.width` is `None` and `kind == "seat"`. A malformed
  segment raises when the skill reads the anchor.
- `preapproach(standoff=None)` backs off along the anchor's -z: the given distance,
  else the anchor's standoff, else 0.05 m.
- A grasp anchor's +z points into the object (where the TCP goes). A seat anchor
  (`top_center`, `slot_1`) is where an occupant's `bottom_center` lands.
- When geometry is wrong, re-teach the anchor or move the object in the world. Do
  not add offsets in the skill.

## The approach shape

1. `set_gripper(arm, open_width)` before the approach.
2. A free `move_arm` to the pre-approach pose (planned through free space).
3. Only the last centimetres as a straight line: `move_arm(arm, grasp,
   straight_line=True, tcp_speed=0.03)`.
4. Close to `grasp.width`, `attach`, then lift straight: `move_relative(arm,
   (0, 0, 0.10), tcp_speed=0.08)`.

`stop=False` on a free leg passes through the waypoint instead of settling there
(the next move blends from it); keep the default `stop=True` before a contact, a
gripper close or anything the next step reads. A free `move_arm` / `move_relative`
takes `posture=` to keep the goal on one joint branch (see `transition-poses.md`).

## Contact is declared, everything else stays checked

```python
with contact(ARM, plate_id, source_id):      # open it at the pre-approach, in free space
    move_arm(ARM, grasp, straight_line=True, tcp_speed=SLOW)
    set_gripper(ARM, grasp.width)
    attach(ARM, plate_id, snap_anchor="grasp_short")
    move_relative(ARM, (0.0, 0.0, HOVER_M), tcp_speed=LIFT)
```

- A target covers the object, what sits in or on it and what it sits on;
  `only(obj)` / `only(obj, "drawer")` narrows to the object or one link.
- `parts="fingers"` (default) lets the fingers touch and keeps the rest of the
  gripper 5 mm off. `"palm"`, `"gripper"`, `"held"`, `"arm"`, `"side"` or one part
  name widen it; `floor=` sets a minimum gap instead of "not checked".
- One move only: `allow=contact(arm, target)`.
- **After `release`, the open fingers still touch the object**: the retreat needs
  `allow=contact(arm, obj)` (or stays inside the scope), or it is refused before it
  starts.

## Holding and placing are booked

- `attach(arm, obj, snap_anchor="grasp")` after the gripper closed: the object now
  is booked as held, so the World (and the planner built from it) carries it with
  the TCP. `snap_anchor` books that anchor exactly at the TCP.
- Place by computing the TCP pose that puts the object's `bottom_center` on the seat,
  from the rigid grip:

  ```python
  grip = get_tcp_pose(ARM).inverse() @ get_anchor_pose(plate_id, "bottom_center")
  seat = dest.pose @ grip.inverse()
  above = seat.translated((0.0, 0.0, 0.10), frame="world")
  move_arm(ARM, above, keep_upright=True)            # carry level
  with contact(ARM, dest_id, plate_id):
      move_arm(ARM, seat, straight_line=True, tcp_speed=SLOW)
      release(ARM, width=OPEN_M, onto=(dest_id, "slot_1"), settle=dest.pose, settle_anchor="bottom_center")
  move_arm(ARM, above, straight_line=True, tcp_speed=LIFT, allow=contact(ARM, plate_id))
  ```

- `release(arm, width=, onto=(holder, anchor), settle=)` opens and books where the
  object came to rest; without `settle` it is booked where the arm holds it now.
- Bookkeeping only, no motion: `set_object_pose`, `seat` (a person loaded it),
  `set_articulation` (writes the World only; moving the physical object is the
  skill's job).
- Booking asserts, it does not measure: a marginal real grasp still books clean.

## Lids, doors, drawers: follow the anchor's arc

```python
start, end = get_articulation(shaker_id)["lid_joint"], 1.666
grip = anchor(shaker_id, "lid_grip")
move_arm(ARM, grip.preapproach())
with contact(ARM, shaker_id):
    move_arm(ARM, grip, straight_line=True, tcp_speed=SLOW)
    set_gripper(ARM, grip.width)
    move_path(ARM, sweep_anchor_steps(shaker_id, "lid_grip", "lid_joint", start, end, 12, 0.06))
    set_gripper(ARM, OPEN_M)
```

`sweep_anchor_steps` evaluates the anchor at each interpolated joint angle; each
step predicts that angle, and the World takes the last one when the arm reaches it,
so the next skill plans against the lid where it is. `interp_anchor_steps` goes from
one anchor to another along a straight line.

## Plan scopes

`with plan_scope(name, *values):` keys the planned moves inside by `name` and
`values` (ids, names, numbers) instead of by all the skill's inputs, so an approach
that depends only on (object, tool) is planned once and reused for every well or
volume. Values must not be measured readings (a pose or array raises `TypeError`).

## live_state.yaml

Read `references/live-state.md` before writing skills that use tips, wells or
calibration. Key strictly by instance id; nested maps are replaced wholesale.

## Run-scoped state

- `set_skill_variable` / `get_skill_variable`: cleared when a workflow run or a CLI
  run starts, and at no other time (a sim run from the Skills Editor keeps what the
  last run left).
- `from execution.skill_editing import shared_state`: a module namespace, never
  cleared between runs.

Treat both as possibly stale: overwrite at the start of the producing skill and
raise a clear error when a consumer finds nothing.

## Sim honesty

- `is_sim_mode()` is true on the sim set. Gate hardware-only side effects with it
  (instrument HTTP calls, Slack posts that must not go out from a sim run).
- `epipette_*` motor verbs do not actuate on the sim set; they return a simulated
  success.
- Use `pause_aware_sleep(s)` for waits: it honours pause and stop, and on the sim set
  it is divided by the sim pace.

## Credentials: Secrets, never code

- Never hardcode a token or pass one as a workflow input. The machine's Secrets
  hold it; the skill names it: `api_request(url, auth_secret="NAME")` for a bearer
  token, `get_secret("NAME")` for anything else (check for `None` first).
- Secret values are not masked: never log, post, save or return one, and never put
  one in a URL.
- Secrets are unavailable online: `get_secret` returns the default and an
  `auth_secret` request is not sent (`success: False`).

```python
result = api_request(url, method="POST", json_body=body, auth_secret="INSTRUMENT_API_TOKEN")
if not result["success"]:
    raise RuntimeError(f"API call failed: {result['error']}")
```

## Reliability: attempt, verify, retry, escalate

This lives in the meta skill that sequences an instrument's atomic skills:

```python
for attempt in range(2):
    _attempt_attach(...)
    if _tip_present():        # a sensor reading, not hope
        return {"success": True}
    _cleanup_partial(...)     # undo before retrying
pause_for_user("Tip attach failed twice: fix the tip box and resume.")
```

Escalation, in order: `print_log` -> `send_slack` -> `ask_user_slack` (a question;
returns the choice) -> `pause_for_user` (blocks until the operator resumes). A
refused move (`SkillError`) is not a retry candidate: fix the target.

## SkillObject

A `SkillObject` has `.id` (the instance id) and `.pose`, a 12-float list
`[centroid xyz, roll pitch yaw, extent xyz, origin xyz]`. Prefer `resolve(obj)` and
anchors; `get_object_pose(obj)` gives the object frame (the `object` anchor) as a
`Pose`, which is not the mesh centroid.
