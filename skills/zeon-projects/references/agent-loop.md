# The agent loop: your sim instance, runs, and links for the human

> Hosted docs: [The development loop](https://readme.zeonsystems.app/docs/the-development-loop.md) · [Running a workflow in the cloud sim](https://readme.zeonsystems.app/docs/running-a-workflow-in-the-cloud-sim.md) · [CLI reference](https://readme.zeonsystems.app/docs/cli-reference.md). The hosted pages may predate the agent verbs below; `zeon <verb> --help` is authoritative.

You develop against a **cloud sim instance** of the lab cell. It runs the copy of the project it loaded from the cloud, never your folder. A human usually watches the 3D viewer while you work. The session is simulation only; real hardware is not reachable from it.

## The loop

```
zeon login                         # the USER runs it (browser sign-in); you never handle the token
zeon new project NAME [DIR]        # or: zeon clone PROJECT [DIR]  /  zeon init (adopt this folder)
# ... edit files ...
zeon sync                          # commit + merge the cloud + push; refreshes a loaded instance
zeon up [--world W]                # load the pushed project + its world on your instance; prints the viewer link
zeon brief                         # project, setup, world + objects/seats, skills + inputs, workflows, last runs
zeon run NAME [-i k=v ...] [--world W] [--detach] [--timeout S]
zeon wait ID   /   zeon logs ID [-f]
zeon py '<code>'   /   zeon py -f scratch.py      # the sim REPL (skill API names, sim, skills, brief, ...)
zeon snap out.png                  # a picture of the sim viewer (rendered on the instance)
zeon say "text"   /   zeon look TARGET            # narrate / point the camera (object, holder.anchor, viewer.yaml preset)
zeon open [--workflow W | --canvas W]             # links for the human (below)
zeon down                          # release the instance when done (a run still going keeps it)
```

- `zeon up` is needed once, after an instance restart (exit 6 / a 503: wait about 60 s, `zeon up`, retry), and when a push printed no "instance refreshed". A restart resets the sim world: earlier runs' effects are gone.
- `zeon push` / `zeon sync` refresh a loaded instance and print "instance refreshed" (the loaded world is kept; `--world W` reloads one; `--no-refresh` skips it).
- `zeon clone` and `zeon init` write `AGENTS.md` and `CLAUDE.md` when the project has none (`--no-agent-guide` skips); they never overwrite one. Read the project's copy first.
- Every verb takes `--json` (one JSON object on stdout, errors included); commands never prompt; every error ends with a `next:` line. Exit codes: 0 ok, 1 the entry or run failed, 2 usage, 3 not signed in / token rejected / REPL not enabled, 4 the REPL guard refused the code, 5 timed out (the run continues), 6 instance unavailable.
- `zeon py`, `zeon run`, `zeon brief` print `notice: ...` lines on stderr when the instance does not run what your folder has (unpushed edits -> `zeon sync`; unpushed commit -> `zeon push`; another project or an older copy loaded -> `zeon up`; the cloud moved on, e.g. the human saved in the app -> `zeon pull`). Act on them before reading a failure as a bug in your code.

## Reading `world_missing`

`zeon up` loads the world and reports the objects that did **not** load: text `warning: world W loaded WITHOUT N object(s)` with `id (type): reason` rows, or `world_missing: [{id, type, reason}]` in `--json` (`zeon brief` shows the same as `world.missing`). The world still loads; a skill that names a missing object fails with "no object". The cause is a type that is neither in the project's `objects/` nor in the mesh-database catalog your org can see. Fix it before running: `zeon new object TYPE` when the catalog has it, otherwise change the world.

## Runs

- `zeon run NAME` takes a skill id, or a workflow id / app display name (`--kind skill|workflow` to force). `-i key=value` sets an input (value parsed as JSON when it parses); unset workflow inputs take their declared `defaultValue`.
- A workflow run executes the instance's copy of `workflows/<id>.json` as it is now (`from_project`), not a graph the app's editor stored earlier. So `zeon sync` before `zeon run`, or you run the old graph.
- `--world W` reloads that world before the run (the run itself waits on the load): use it to reset a sim left half-done by a failed run.
- The default wait is 120 s and the run keeps going after it. For workflows use `--timeout 600`, or `--detach` then `zeon wait ID` / `zeon logs ID -f`. Ctrl+C on `zeon run` cancels the run (a Stop).
- A skill that raises **fails** a sim run: `zeon run` / `zeon wait` exit 1 and `zeon logs ID` shows the step that failed. CLI sim runs never hold. Run control and Stop: `references/execution-model.md`.
- A timeout while the run waits on an `ask_user_slack` prompt says so ("an ask_user_slack prompt waits for an answer, in Slack or the app"; `"waiting_on_prompt": true` in `--json`). Only a human can answer it: tell them, then `zeon wait ID`.
- The first run after a skill edit is slow: every planned move is solved again. See the plan cache in `references/execution-model.md`.

## Links for the human

| Command | Opens |
|---|---|
| `zeon open` | the instance's 3D viewer (`--viewer NAME` for another) |
| `zeon open --workflow W` | the web app's run screen on workflow W (graph and inputs) |
| `zeon open --canvas W` | the same run screen on its **Inputs** tab, with W's canvas rendered against the sim |

- `--workflow` / `--canvas` take an id or the display name; `--world W` selects a world (default: the one the sim has loaded); `--browser` also opens it locally. The link opens on the same account, so it reaches your instance.
- It shows the **pushed** version: `zeon sync` first. A link entry never clears the sim's loaded world.
- The CLI refuses (exit 2) when the project is not the instance's active one: run `zeon up` first. A link to another project would switch the instance under you. `--canvas` is refused when the workflow has no enabled React `canvas_ui`.
- On a link entry the page follows your pushes: it re-reads the workflow and the canvas source every 3 s while the tab is visible and updates in place. The graph does not follow during a run (it catches up after) or over the human's unsaved edits. A changed canvas remounts fresh: typed values and Confirm reset, and Run stays held until the human presses **Confirm setup** again. Tell them when you pushed a canvas change.

## REPL rules

The REPL (`zeon py`) has the skill API names plus `sim`, `skills` (`skills.<id>(**params)` runs a skill), `run_workflow`, `snapshot`, `say`, `look` and `brief`. It acts on the sim only. A guard refuses (exit 4) reading the environment, credentials, platform source or internals, and importing `execution.*` other than `execution.skill_api`. Every entry and every run is logged with the account. Rewrite refused code with the skill API; resubmitting the same code gets the same answer.
