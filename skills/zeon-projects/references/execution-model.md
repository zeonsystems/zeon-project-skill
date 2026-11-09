# How the executor actually runs a workflow

> Hosted docs: [Authoring a workflow](https://readme.zeonsystems.app/docs/authoring-a-workflow.md) · [The workflow file](https://readme.zeonsystems.app/docs/workflows-json.md) — this file goes further than either.
>
> Skill API v2 verbs raise a `SkillError` on failure (a refused or stalled move,
> an unknown object), so an unguarded failure fails its node by the rule below.

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

## `$input` resolution and object inputs

Input values flow into state at run start; an input the run does not set takes its declared `defaultValue`. A
value becomes an object reference (`{"object_ref": <value>}`) only when its input is **declared** `object`, and
then it resolves as an instance id or a unique display name. Inputs declared `string` / `int` / ... pass through
as they are, even when they hold a UUID. Only an input with **no** declared type falls back to a shape test (a
string containing a UUID is treated as an object reference, and the lookup miss aborts the skill): declare
every input's `type`.

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

## Run control: Stop, pause and prompts

- **A Stop is final.** Once a run is cancelled, a Pause, Resume or step that arrives later cannot make it live
  again. Ctrl+C on `zeon run` sends a Stop. To go on, start a new run (or the human resumes from a checkpoint
  in the app's Resume run).
- **A Stop ends an open `ask_user_slack` prompt at once**: the skill raises the cancel and the run ends
  cancelled, not failed (the Slack message shows the cancel).
- **A pause stops a prompt's timeout counting**: `timeout_s` counts only unpaused time, and the prompt stays
  answerable in the app and in Slack while paused.
- A `zeon run` / `zeon wait` timeout on a run waiting for a prompt says so (`waiting_on_prompt` in `--json`):
  the run is waiting for a human, not stuck.
- **Sim runs from the CLI fail; they never hold.** A skill that raises ends the run failed (exit 1); read
  `zeon logs ID`, fix, sync, run again. Holds on real-hardware runs are handled by the Zeon team; the status
  the app and CLI read shows such a run as `running`.
- **Rollback to a checkpoint is gone** (the route answers 410 Gone). Resume from a checkpoint remains.

## The plan cache

Each skill keeps the moves it planned in `skills/<id>/.motion_plan_cache.pkl` (written by the platform, synced
with the project, never authored). A move in a skill run is keyed by **the skill's source digest + the skill's
inputs + the move's position in the run**, and is reused when the command and the nearby world match;
otherwise it is solved again (the miss says why: "first run", "new command", "world changed", ...).

- The source digest hashes every `.py` file in the skill's folder **and every `.py` directly in `skills/`**
  (`skills/utils.py`, ...). Editing `skills/<id>/*.py` invalidates that skill's plans; editing a top-level
  `skills/*.py` invalidates **every** skill's plans. Re-syncing identical bytes does not.
- Different inputs are different keys: the first run with new inputs solves its moves.
- So: **don't edit skill code between the runs of a series** (a comparison, a repeat-until-it-works loop on
  timing). Batch the edits, sync once, and expect the first run after them to be slow; the runs after it reuse
  the plans.
- `with plan_scope(name, *values):` keys the moves inside by `(source, name, values, ordinal in the block)`
  instead of all the inputs, so an approach that depends only on, say, the object is planned once for every
  well and volume (`references/skills.md`).
- In the platform's service log, the load line reads `motion: plan cache <skill> in memory N, read M (...)`,
  and each move's line names the cache outcome (`plan cache <skill> move <n> hit` / `miss (<why>)`) with the
  solve time split by phase.
