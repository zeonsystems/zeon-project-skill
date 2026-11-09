# Transition poses and postures: known arm configurations

> Hosted docs: [Arm motion and the gripper](https://readme.zeonsystems.app/docs/arm-motion-and-the-gripper.md) · [Skill authoring patterns](https://readme.zeonsystems.app/docs/skill-authoring-patterns.md)

A **transition pose** is a named joint configuration (six joint values, rad) that a
skill starts or ends at, or passes through when it relocates an arm. A **posture**
tells a free Cartesian move which joint branch to resolve its goal on. Both keep an
arm's shape predictable from run to run.

## What the planner already does

Every v2 motion verb is planned and collision-checked (both arms, the world, held
objects) before the arm moves; a move that cannot be made raises a `SkillError`
naming the reason. So a transition pose is not there to avoid collisions the planner
would miss. It is there for:

- **Composition.** A skill that ends at a known joint pose leaves the next skill a
  known start, whatever ran before. End every skill with `move_arm_js(arm, HOME)`.
- **Branch control.** A free `move_arm` resolves its goal configuration from where
  the arm is, then across the target's pose set, then by a global search. From an
  unusual start that can land on another elbow or wrist branch. A joint target has
  no such choice.
- **Reach.** Some targets are only reachable from one side; routing through a pose
  on that side first makes the final approach reliable.

## Using them

- Write the values as literals in the skill or in `skills/utils.py`
  (`from utils import LEFT_FORWARD_DOWN`). `move_arm_js` refuses a string. Do not
  alias one constant to another; write each one out.
- The project's own poses win: they were taught for that bench and that setup. Copy
  the starter skills' `HOME` constants as the pattern.
- Several waypoints as one planned move: `move_arm_js(arm, q, via=[q1, q2])` (all
  six values each).
- Route through the nearest pose; chain poses when crossing the workspace rather
  than one long jump. End on an anchor-driven approach, never on a transition pose
  as the work pose.

## Naming convention (optional)

Projects that keep a family of transition poses name them by **azimuth** and
**wrist**: `FORWARD` (over the deck), `OUTER` (away from the other arm), `INNER`
(toward it), `BACK`; `DOWN` (TCP pointing at the deck) or `FRONT` (TCP horizontal).
`INNER` / `OUTER` instead of left / right keeps one name meaningful on both arms.
Where joint 1 wraps behind the arm, keep two poses for the same spot
(`BACK_DOWN_FROM_INNER` / `..._FROM_OUTER`) and pick the one on the arm's current
side so the base does not unwind the long way.

## Postures

A free `move_arm` / `move_relative` (no straight line, no `keep_upright`) takes
`posture=` to resolve its goal on one branch:

```python
POSTURE = {"q": [0.84, 0.52, -0.61, 2.02, -0.84, -2.20],
           "prefer": {"joint1": [0.0, 6.2832], "joint5": "negative"},
           "off_branch": None}
move_arm(ARM, target, posture=POSTURE)
```

- `q` seeds the search; `prefer` is per joint a sign (`"negative"` / `"positive"`)
  or a range `[lo, hi]` (rad).
- If no configuration on the branch passes, the goal resolves as without a posture
  and the deviation is logged, except a held carry that would change branch, which
  is refused. `"off_branch": "log"` / `"refuse"` overrides that.
- The skill owns its postures, per move: there is no project or per-run default.
- Straight lines, `keep_upright`, `move_path` and `via` take no posture (a straight
  line keeps the branch it starts on).

## Two arms

A move of one arm holds the other still and plans against it. When both must move,
`run_parallel({"left": fn_l, "right": fn_r})` plans the legs on one model so each is
checked against the other's planned motion. Before swinging an arm toward the
centre, clear the other arm first as an explicit step: the planner refuses the move
rather than moving the other arm for you.
