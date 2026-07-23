# Transition poses — safe waypoints for relocating an arm

Transition poses are a fixed set of named joint configurations for each arm,
used as **safe intermediate waypoints** when moving between tasks or
instruments — never as grasp targets themselves. To relocate an arm, send it
to the appropriate transition pose (or a short chain of them) as `move_arm_js`
targets *before* commanding the final approach. This keeps the slew retracted
and predictable instead of planning a free-space path between arbitrary start
and goal configurations.

## Why this matters — use these by default when a skill relocates an arm

- **IK reliability.** A `move_arm_js` target *is* the joint configuration —
  there is no IK solve, so the move cannot fail IK or flip to an awkward
  elbow branch. A long free-space Cartesian `move_arm` must solve IK from
  whatever configuration the arm happens to be in (`max_ik_retries=3`) and
  can fail or pick a wrapped solution mid-run. Routing the slew through
  transition poses and starting the final Cartesian approach from the
  nearest one also gives the IK a consistent seed — the same approach
  solves the same way every run.
- **Modularity.** A skill that **begins and ends at (or near) a transition
  pose** composes with any other skill without pairwise path planning —
  whatever ran before, the arm is in a known, retracted configuration.
  This is what makes meta-skills pure sequencing.

Skipping transition poses for a cross-workspace move should be a deliberate,
stated choice, not a default.

## Naming grid

Each pose is named by two axes:

- **Azimuth** — the direction the arm is turned: `FORWARD` (over the deck),
  `OUTER` (away from the centerline), `INNER` (toward the other arm), `BACK`
  (behind). Inner/outer rather than left/right so the names are
  **arm-agnostic**.
- **Wrist orientation** — `DOWN` (gripper pointing at the deck, TCP along −Z)
  or `FRONT` (gripper pointing horizontally outward, TCP along the arm's +X).

This gives a compact grid (`OUTER_DOWN`, `INNER_FRONT`, …) that decouples
poses from specific instruments: an instrument is reached by routing through
the nearest transition pose.

**The BACK exception**: `BACK` sits on the centerline seam where joint 1
wraps, so it splits into `BACK_DOWN_FROM_INNER` / `BACK_DOWN_FROM_OUTER` —
the same physical spot, one full base turn apart. A skill picks the branch
matching the arm's **current side** so the base never unwinds the long way
around.

## Coordinate frame

Azimuth names map to directions in each arm's base frame (X forward,
Y lateral, Z up). The Y axis is **mirrored between the two arms** — which is
exactly why the poses are named INNER/OUTER instead of left/right: the same
name is a +Y motion on one arm and −Y on the other.

| Azimuth | Left arm | Right arm |
|---------|----------|-----------|
| FORWARD | +X       | +X        |
| BACK    | −X       | −X        |
| INNER   | −Y       | +Y        |
| OUTER   | +Y       | −Y        |

`DOWN` points the TCP along −Z (at the deck); `FRONT` points it along the
arm's +X. Because INNER/OUTER are defined by the arm's own Y sign, a single
`INNER_DOWN`/`OUTER_DOWN` definition means "toward / away from the
centerline" on either arm without rewriting it per side.

## Canonical pose tables

Left arm:

```python
LEFT_FORWARD_DOWN        = [-0.104, -0.681, -0.963, -0.018, 1.626, 1.459]
LEFT_FORWARD_FRONT       = [0.085, -0.196, -0.767, -3.020, 0.636, 3.023]
LEFT_OUTER_DOWN          = [1.464, -0.695, -0.720, -6.281, 1.416, 4.616]
LEFT_OUTER_FRONT         = [1.261, -0.506, -0.448, -4.879, 1.833, 4.080]
LEFT_INNER_DOWN          = [-1.331, -0.882, -1.054, 0.002, 1.933, 1.880]
LEFT_INNER_FRONT         = [-0.750, -0.317, -0.471, -0.848, 2.141, 2.591]
LEFT_BACK_DOWN_FROM_INNER = [-3.291, -0.576, -1.212, 0.009, 1.784, -0.077]
LEFT_BACK_DOWN_FROM_OUTER = [2.986, -0.577, -0.797, 0.002, 1.374, -0.077]
```

Right arm:

```python
RIGHT_FORWARD_DOWN        = [-0.218, -0.663, -0.989, -0.031, 1.682, 4.491]
RIGHT_FORWARD_FRONT       = [0.250, 0.112, -0.858, -1.347, 1.777, 2.382]
RIGHT_OUTER_DOWN          = [-1.583, -0.554, -1.089, -0.043, 1.639, 1.595]
RIGHT_OUTER_FRONT         = [-0.810, 0.200, -1.095, -1.008, 2.165, 2.442]
RIGHT_INNER_DOWN          = [1.675, -0.730, -0.815, 0.043, 1.567, 4.833]
RIGHT_INNER_FRONT         = [0.729, -0.236, -0.731, 1.030, 2.242, 3.955]
RIGHT_BACK_DOWN_FROM_INNER = [3.063, -0.335, -1.281, 0.026, 1.584, -0.077]
RIGHT_BACK_DOWN_FROM_OUTER = [-3.095, -0.421, -1.313, 0.008, 1.692, 0.087]
```

`FORWARD_DOWN` is the same configuration the default scaffold ships as
`LEFT_ARM_STOW_JOINTS` / `RIGHT_ARM_STOW_JOINTS` — treat them as one pose,
don't define both.

## Using them in skills

- **Constants live in the project**, per platform convention: define them in
  `skills/utils.py` and `from utils import …` in skill code. If the project
  already defines transition poses (any naming), **the project's values win**
  — they may be calibrated for that bench. Copy the canonical tables in only
  when the project has none.
- Reference by name as `move_arm_js` targets (joint-space speeds, e.g. `0.5`):

  ```python
  from utils import LEFT_OUTER_DOWN, LEFT_FORWARD_DOWN

  move_arm_js(arm="left_arm", joint_angles=LEFT_FORWARD_DOWN, speed=0.5)  # retract
  move_arm_js(arm="left_arm", joint_angles=LEFT_OUTER_DOWN, speed=0.5)    # swing out
  # ...then the final anchor-driven approach (references/patterns.md)
  ```

- Route through the **nearest** pose; chain poses when crossing azimuths
  (e.g. INNER → FORWARD → OUTER) rather than jumping across the workspace in
  one move.
- For BACK, pick the `FROM_INNER` / `FROM_OUTER` branch that matches where
  the arm currently is.
- Transition poses are waypoints: end on an anchor-driven approach, never on
  a transition pose as the work pose.
