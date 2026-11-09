# Motions: recorded tool paths stored beside an object

> Hosted docs: [Motions](https://readme.zeonsystems.app/docs/motions.md) · [Recording a motion](https://readme.zeonsystems.app/docs/recording-a-motion.md) · [The object model file](https://readme.zeonsystems.app/docs/objects-object-model-yaml.md)

An anchor names a place; a **motion** names a path through places, recorded by
hand-guiding a real arm in the annotation editor. Both live in the object's frame,
so both follow the object when it is re-localized.

## Skills cannot replay a motion today

Skill API v2 has **no replay verb**. The v1 `play_object_motion` (and v1
`interpolate_anchor_to_anchor` / `interpolate_anchor_joint_path`) raise
`NotImplementedError`; `list_object_motions` / `load_object_motion` are not in the
v2 surface. To follow a path in a skill, build it from anchors as `move_path` steps:

- an arc of an articulated part: `sweep_anchor_steps(obj, anchor_name, joint,
  start_angle, end_angle, steps, tcp_speed)`;
- a straight run between two anchors: `interp_anchor_steps(obj, a0, a1, joints,
  steps, tcp_speed)`;
- your own waypoints: `move_path(arm, [Step(pose, straight_line=True,
  tcp_speed=0.03), ...])`. All steps are one planned, collision-checked goal.

If a recorded motion is the only description of a path, teach anchors at its key
points and build the steps from them. Do not copy keypose numbers into code.

## How a motion is stored

In `objects/<type>/motions.yaml`, next to the object model (never inside it: the
object-model loader refuses a `motions:` key and the object fails to load):

```yaml
format: motions/1
motions:
  lid_lift:
    parent_link: lid             # required, a URDF link
    description: Lift the lid off
    gripper_variant: wellplate   # omitted when stock
    keyposes:                    # at least two (one pose is an anchor)
      - t: 0.0                   # seconds from start; >= 0, never decreasing
        link_T_tcp: {xyz: [0.012, -0.004, 0.18], wxyz: [0.0, 1.0, 0.0, 0.0]}
        seed: [0.104, -0.412, 0.203, 0.0, 1.108, 0.301]   # optional joint hint
        gripper: 0.03                                      # optional, m, >= 0
```

Loader-fatal: a `format` other than `motions/1`, a key outside the format, a
`parent_link` not in the URDF, fewer than two keyposes, a negative or decreasing
`t`, a negative `gripper`. `scripts/validate.py` checks all of these. A motion name
may equal a URDF link name (motions are not frames of the kinematics).

Never hand-write or edit keyposes; record them. A motion records the gripper it was
demonstrated with; any path derived from it is only valid for that gripper.
