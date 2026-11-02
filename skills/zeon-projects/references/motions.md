# Motions — recorded tool paths stored on an object

> Hosted docs: [Motions](https://readme.zeonsystems.app/docs/motions.md) · [Recording a motion](https://readme.zeonsystems.app/docs/recording-a-motion.md) · [The object model file](https://readme.zeonsystems.app/docs/objects-object-model-yaml.md)

An anchor names a place; a **motion** names a path through places. Both live in
the object's own frame, so both follow the object when it is re-localized —
that is the whole point. Use a motion when the useful part is the *shape* of
the path: lifting a lid off its hinge, easing a plate out of a slot at an
angle, sweeping a tool along a channel.

Motions are **recorded by hand-guiding a real arm**, in the annotation editor's
Motions tab, and played there (*Play on arm*). You do not author them, and you
do not hand-write keypose lists — read a `motions:` block to learn what an
object can do, and record new ones in the editor.

## Replaying a motion from a skill: not in the skill API v2 yet

The skill API v2 has **no motion-replay verb yet**. The v1 verbs
`list_object_motions` / `load_object_motion` / `play_object_motion` belong to
the legacy API, and `play_object_motion` is retired: it raises
`NotImplementedError` on the current platform (validate.py flags the call).

Until a v2 verb exists, a skill that needs a shaped path builds it from
anchors and runs it as one planned, collision-checked goal:

```python
steps = [Step(anchor(reader, "lid_grip").pose, straight_line=True, tcp_speed=0.02),
         Step(anchor(reader, "lid_lifted").pose, straight_line=True, tcp_speed=0.05)]
move_path(ARM, steps)
```

or, for an arc that follows an articulation, `sweep_anchor_steps(...)`
(`references/patterns.md`, "Articulated objects"). The anchors are taught in
the annotation editor like any other; a recorded motion's keyposes are a good
guide to where they belong. If the user needs a recorded motion replayed
verbatim, say that the current API has no verb for it rather than inventing
one.

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
  traces a path offset by the difference between the two tool tips. The
  editor's *Play on arm* warns. Confirm the arm is wearing what the motion was
  recorded with. Anchors carry `gripper_variant` too (`anchor(...).gripper_variant`):
  compare it with the fitted gripper before trusting a taught grasp.
- **Editing a keypose drops its joint seed**, so a heavily edited motion can
  replay with the arm in a different shape than demonstrated. Prefer re-recording
  over editing when the arm's configuration matters.
- Start slow. The editor's speed slider starts at 20 mm/s for a reason; crawl a
  path you don't trust before winding it up.
