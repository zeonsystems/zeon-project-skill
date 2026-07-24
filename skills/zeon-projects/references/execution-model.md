# How the executor actually runs a workflow

> Hosted docs: [Authoring a workflow](https://readme.zeonsystems.app/docs/authoring-a-workflow.md) · [The workflow file](https://readme.zeonsystems.app/docs/workflows-json.md) — this file goes further than either.

The runtime semantics below are not guessable from the file formats, and several
are counter-intuitive. They determine whether the code you author does what the
user thinks it does. (Verified against the platform's graph executor.)

## Failure is exception-driven — return values do not route

- A skill that **returns without raising counts as success**, no matter what it
  returns. `return {"success": False}` still takes the `on_success` edge.
  **To fail a node, raise an exception.**
- When a skill raises, the executor swallows the exception into state
  (`last_skill_error`) and routes along `on_failure` edges. The run doesn't
  crash — it follows the graph.
- A `default` edge is **unconditional**: out of a skill node it fires even after
  the skill raised. Use `on_success` between sequential skill nodes; a `default`
  edge out of a skill means "continue even on failure," which is almost never
  what the user wants after a failed grasp.
- The returned dict *is* stored (as `skill_result`) — that's how conditional
  nodes read it — and `success` is the reporting convention. So: return
  `{"success": True, ...}` on the happy path, **raise** on failure.

## `retry` on a skill node is a no-op

The executor never reads a `retry` field on skill nodes. Don't offer it as
error handling — build retries inside the skill (attempt → verify → retry →
escalate; see `references/patterns.md`) or as explicit graph structure.

## Conditional nodes: a tiny expression grammar

Supported expressions, exactly: a bare variable (`tip_present`), one equality
(`status == ok`), or a literal `true`/`false`. Anything else — `count < 5`,
`a != b`, `x and y` — is treated as a single state-key name and **KeyErrors when
the node executes**, typically mid-run.

Variables resolve from top-level state (workflow inputs) first, then from the
**immediately preceding skill node's returned dict** (`skill_result`, which every
skill node overwrites). To branch on something a skill learned, return it in
that skill's result dict and put the conditional node directly after it.

## Loop nodes

- `type: "count"` — `iterations: N`.
- `type: "collection"` — `source` must name a **declared workflow input**
  (normally `is_array: true`). If the key is missing from state, the collection
  is silently empty: the loop body runs **zero times and the run reports
  success**. This is the most deceptive failure available — validate.py checks
  it.
- `type: "conditional"` — the expression supports exactly **one** comparison
  (`<`, `>`, `<=`, `>=`, `==`, `!=`), no `and`/`or`.
- Inside a collection loop, a skill receives the current element through a
  parameter literally named **`current_item`** — declare it in the skill's
  signature; the engine injects it.
- Loop `node_id`s must be identifier-safe (`fill_loop`, not `fill-loop`). A
  hyphenated id kills the run **mid-run** with a baffling internal name error
  the first time the loop's edges are evaluated — possibly after the robot has
  already executed earlier motion nodes; ids with spaces fail earlier, at
  graph build.

## How parameters reach a skill

The engine binds keyword arguments **by name from the execution context**
against the skill function's signature:

- A required parameter (no default) with no bound value **aborts the node**:
  `Skill 'x' requires parameter 'y'`.
- A bound key that isn't in the signature is **silently dropped** — a typo'd
  optional parameter means the robot runs with the default and no error.
- A parameter annotated `SkillObject` receives `SkillObject(id, pose)`; the
  same value bound to an *un-annotated* parameter degrades to the raw
  12-float pose array.

Reserved state keys — never name a skill parameter any of: `skill_result`,
`last_skill_success`, `last_skill_error`, `condition_result`,
`execution_completed`, `execution_id`, `node_id` (you'd receive engine data,
not your value). `current_item` is reserved too, but deliberately: declaring
it is how loop injection works.

## `$input` resolution and the UUID trap

Input values flow into state at run start. Object-typed inputs resolve world
objects by name. One sharp edge: **any string value containing a UUID anywhere
is auto-treated as a world object reference** — a barcode or filename shaped
like a UUID gets "resolved" against the world and the lookup miss aborts the
skill. Don't route UUID-shaped strings through string inputs or defaults.

## Saving is not validating

The gateway **saves workflows even when validation fails** — errors come back
in the response, but the file persists. A successful save in the editor or via
the API is not evidence the graph is runnable. `scripts/validate.py` is the
gate. Also on every save the server rewrites `updated_at`, fills `created_at`,
and strips null-valued fields — don't fight that churn in diffs.

## Conditions in metadata.yaml

`postconditions` are **applied, not verified**: on success their key/values are
written into execution state for later nodes to read. `preconditions` are
parsed but currently bypassed by the executor.
