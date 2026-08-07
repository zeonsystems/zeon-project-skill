# Motions — recorded tool paths stored on an object

> Hosted docs: [Motions](https://readme.zeonsystems.app/docs/motions.md) · [Recording a motion](https://readme.zeonsystems.app/docs/recording-a-motion.md) · [The object model file](https://readme.zeonsystems.app/docs/objects-object-model-yaml.md)

An anchor names a place; a **motion** names a path through places. Both live in
the object's own frame, so both follow the object when it is re-localized —
that is the whole point. Use a motion when the useful part is the *shape* of
the path: lifting a lid off its hinge, easing a plate out of a slot at an
angle, sweeping a tool along a channel.

Motions are **recorded by hand-guiding a real arm**, in the annotation editor's
Motions tab. You do not author them, and you do not hand-write keypose lists —
read a `motions:` block to learn what an object can do, and record new ones in
the editor. A skill's job is to *replay* one.

## The three functions

```python
list_object_motions(object_name, index=None) -> list[str]

load_object_motion(object_name, motion_name, index=None, joint_config=None) -> dict

play_object_motion(
    arm, object_name, motion_name, *,
    speed=0.10, accel=None, max_total_accel=None, time_scale=1.0,
    index=None, joint_config=None, blend_radius_mm=None,
    apply_gripper=True, executor=None, wait=True,
) -> dict
```

Everything after `motion_name` on `play_object_motion` is keyword-only.
`list_object_motions` returns names sorted, or `[]`. `load_object_motion` is
read-only — it resolves and reports, it never moves the arm.

## These three raise — unlike most of the runtime API

This is the trap. The device verbs and `api_request` fail soft and hand you a
result dict to branch on. **The motion functions raise instead.** There is no
`{"success": False}` to check.

Per `execution-model.md`, a raised exception is exactly what fails a node, so
an unguarded motion failure aborts the workflow at that node — which is usually
right. Wrap in `try` / `except` only when a failure genuinely should not end
the run, and route the failure edge deliberately.

A missing object or motion raises `KeyError` / `ValueError` / `FileNotFoundError`
before anything moves. `KeyError` for an unknown motion name lists the names
the object does have.

`play_object_motion` raises `RuntimeError` for these, all verified against the
platform's replay executor:

| Cause | Has the arm moved? |
|---|---|
| Any compiled sample is unreachable — IK is solved for every sample first, seeded with the joint angles recorded during the demonstration so replay stays on the operator's elbow/wrist branch | **No** — raises before any motion |
| The tool is further than **150 mm** or **45°** from the motion's first keypose | **No** — refuses outright |
| The controller faulted (checked after the run; the vendor call reports nothing itself) | Yes |
| The tool did not finish at the final keypose, within **5 mm** and **0.05 rad** (~2.9°) — this is how a stopped or truncated motion is caught | Yes |
| A gripper command failed (only when `apply_gripper=True`) — the replay stops rather than continue with the jaws wrong | Yes, part-way |

## Get onto the start yourself

Because replay refuses to travel more than 150 mm / 45° to reach its own first
keypose — that approach is a straight line nothing has collision-checked — the
skill must put the arm there first. `load_object_motion` hands you the pose:

```python
def open_reader_lid(reader: str):
    if "lid_lift" not in list_object_motions(reader):
        raise ValueError(f"{reader} has no lid_lift motion")

    motion = load_object_motion(reader, "lid_lift")
    start = motion["keyposes"][0]          # already in world coordinates
    move_arm("right_arm", start["xyz"], start["rpy"])

    result = play_object_motion(
        "right_arm", reader, "lid_lift",
        speed=0.05,            # 50 mm/s
        max_total_accel=0.10,  # bound the corners, not just the straights
    )
    print_log(f"replayed in ~{result['controller_estimate_s']:.1f}s", runlog=True)
    return {"success": True}
```

`load_object_motion` returns keyposes already rebased onto wherever the object
is *now* and onto its current joint configuration, so you can move to one
directly:

```python
{"object_id", "parent_link", "description", "duration_s", "n_keyposes",
 "keyposes": [{"xyz", "rpy", "wxyz", "t", "gripper"}, ...]}   # ordered from start
```

## Tuning the profile

- `speed` (m/s, default `0.10` = 100 mm/s) — peak tool speed along the path.
- `accel` (m/s², default `3 * speed`) — bounds only the **along-path** term, so
  true acceleration is higher wherever the path curves.
- `max_total_accel` (m/s²) — caps *true* Cartesian acceleration, centripetal
  included, by stretching the duration. **Applied last, so it wins.** Reach for
  this rather than `accel` when a tight corner is the worry.
- `time_scale` (default `1.0`) — below 1 always slows down as asked; above 1
  buys speed only until `max_total_accel` binds, after which it does nothing.
- `blend_radius_mm` — how much the controller rounds corners, clamped per
  corner against its own segments. Rounding is right in transit and **wrong for
  a deliberate contact**: it turns a recorded press into a touch. Set it off if
  a press replays too lightly.
- `executor` — leave `None`. Auto-selects from the arm actually in hand, which
  is what keeps replay working on a machine with no physical arms attached.

## The gripper

`apply_gripper=True` (the default) honours the widths the keyposes carry.

**A gripper change part-way along splits the replay**: the arm parks at that
keypose, the jaws actuate while it is stationary, then the next leg runs. That
is deliberate — the path goes to the controller as one uninterruptible command,
and actuating mid-sweep would close the jaws on a moving target. So a motion
that grips something mid-path replays correctly, at the cost of pausing there.
`gripper_events` counts them and `legs` reports the segment count (`legs` is
absent when the motion ran as one).

Set `apply_gripper=False` to replay the path alone and leave the jaws be.

## Reading the result

Branch on `success`. On a real arm you also get `executor`, `samples`,
`waypoints`, `duration_s`, `controller_estimate_s`, `blend_radius_mm`,
`approach_m`, `verified`, `endpoint_error_mm`, `path_length_m`,
`peak_speed_m_s`, `peak_accel_m_s2`, `gripper_events`, `object_id`. The sim
executor returns a shorter dict (no controller/endpoint keys).

**`duration_s` is not how long the arm takes on real hardware.** It is the
compiled profile's duration; the controller is handed geometry plus one scalar
speed and runs its own profile. Use `controller_estimate_s`. Only the sim
executor consumes the compiled profile directly and honours `duration_s`.

## How a motion is stored

In the object's `object_model.yaml`, under a top-level `motions:` map:

```yaml
motions:
  lid_lift:
    parent_link: body            # required, must exist in the URDF
    description: Lift the lid clear of the deck   # required
    gripper_variant: stock       # optional; omitted when stock
    keyposes:                    # required, at least two
      - t: 0.0                   # seconds from start; >= 0, must not decrease
        link_T_tcp:
          xyz: [0.012, -0.004, 0.18]     # metres, in the parent_link frame
          wxyz: [0.0, 1.0, 0.0, 0.0]     # scalar-first quaternion
        seed: [0.104, -0.412, 0.203, 0.0, 1.108, 0.301]   # optional joint hint
        gripper: 0.03                    # optional, metres, non-negative
```

Two differences from anchors:

- **At least two keyposes.** One pose is an anchor — record it as one.
- **A motion name may collide with a URDF link name.** Anchors are injected
  into the kinematic model as frames so their names must be unique against
  links; motions are not injected, so that rule does not apply.

Keyposes are a thinned recording, not a trajectory — replay interpolates, so a
three-keypose motion still runs as a smooth curve.

## Safety

- **A gripper mismatch is silent.** A motion records which gripper was fitted
  when it was demonstrated (`gripper_variant`). Replaying under a different one
  traces a path offset by the difference between the two tool tips, and
  `play_object_motion` does not check. The editor's *Play on arm* warns; a skill
  gets nothing. Confirm the arm is wearing what the motion was recorded with.
- **Editing a keypose drops its joint seed**, so a heavily edited motion can
  replay with the arm in a different shape than demonstrated. Prefer re-recording
  over editing when the arm's configuration matters.
- Start slow. The editor's speed slider starts at 20 mm/s for a reason; crawl a
  path you don't trust before winding it up.
