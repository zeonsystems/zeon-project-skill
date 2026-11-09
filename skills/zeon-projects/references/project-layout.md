# Project layout, manifest, naming, and sync

> Hosted docs: [Key concepts](https://readme.zeonsystems.app/docs/key-concepts.md) · [The project manifest](https://readme.zeonsystems.app/docs/project-json.md) · [The development loop](https://readme.zeonsystems.app/docs/the-development-loop.md) · [CLI reference](https://readme.zeonsystems.app/docs/cli-reference.md) · [Syncing your work](https://readme.zeonsystems.app/docs/syncing-your-work.md)

## Anatomy

```
project.json                     # manifest (below)
CLAUDE.md, AGENTS.md             # the agent guide (one text in both) — read first
README.md                        # orientation (seeded projects)
viewer.yaml                      # optional camera presets for `zeon look NAME` / look() in the REPL
skills/<skill_id>/
├── robotic_code.py              # the skill implementation (required)
├── metadata.yaml                # id/version/description/tags (required)
├── modules.py                   # `from execution.skill_api import *` (skill API v2)
└── .motion_plan_cache.pkl       # written by the platform: the skill's plan cache (synced; never author it)
skills/utils.py                  # optional shared helpers (part of every skill's plan-cache key)
workflows/<workflow_id>.json     # one graph per file
worlds/<world_id>/               # two formats (references/worlds-and-objects.md):
├── world.world                  #   saved: the world itself (what loads)
├── world.world.engine.json      #   saved: per instance type, metadata, seat
├── world_state.json             #   saved: a derived manifest (never read back); old layout: the scene itself
└── live_state.yaml              # run-time state, version 2, keyed by seat (references/live-state.md)
objects/<type>/
├── <type>.urdf                  # kinematics/geometry references
├── <type>.object_model.yaml     # anchors, parts, articulations (strict schema)
├── motions.yaml                 # optional: recorded motions
├── tags.yaml                    # optional: the type's one tagged unit
└── units/<handle>/tags.yaml     # optional: one per physical tagged unit
canvas/<workflow_id>_screen.tsx  # optional run-setup UI per workflow
inputs/<preset>.json             # optional input presets surfaced to canvases (references/canvas.md)
data/                            # run artifacts, keyed per run by execution_id:
├── captures/<execution_id>/     #   camera snapshots (capture_image)
├── logs/<execution_id>/         #   run-log mirrors (print_log runlog lines)
├── api/<execution_id>/          #   saved api_request responses
└── runs/                        #   reserved, local-only — never synced, never authored
executions/<execution_id>/       # run folders the platform writes; only run_log*.jsonl + metadata.json sync
.runtime/                        # platform scratch, local-only
```

A fresh `zeon new project` is seeded with a runnable **starter** (`template.json` in the scaffold): a world, a few objects, two skill API v2 skills, one workflow, `viewer.yaml`, `README.md` and the agent guide describing that deck. `--template NAME` seeds another server-side template. Treat the starter as reference material: copy its patterns into new files; don't overwrite it unless the user asks.

## project.json

```json
{
  "name": "My project",
  "description": "",
  "created_at": "2026-06-20T00:00:00.000Z",
  "updated_at": "2026-06-20T00:00:00.000Z",
  "archived": false,
  "active_workflow": "my_flow",
  "active_world": "my_world",
  "setup": "<rig name>"
}
```

- `name` is a free display string (unique per user in the cloud). Item names are strict (below).
- `active_workflow` → an existing `workflows/<id>.json`; `active_world` → an existing `worlds/<id>/`. Either may be `null`. `zeon up` loads `active_world` unless given `--world W`.
- `setup` names the rig the project is authored for (written only when the template has one). `zeon brief` shows the rig the instance actually runs and warns when the two differ: moves are planned for the loaded rig.
- Repointing `active_workflow` / `active_world` changes what opens and runs by default — do it when the request calls for it, and say so.
- Timestamps are ISO-8601 with milliseconds and a `Z` suffix.

## Naming rules

| What | Rule |
|---|---|
| Item folder / file names (skill, workflow, world, object, canvas) | `^[a-z_][a-z0-9_-]{0,63}$` |
| `skill_id`, `workflow_id`, node ids (in-file identifiers) | `^[a-z0-9_]+$` — use underscores, not hyphens |
| Workflow input names | `^[A-Za-z][A-Za-z0-9_]*$` |
| Versions (`version` fields) | semver `^\d+\.\d+\.\d+$`, e.g. `1.0.0` |

A skill's Python function name must equal the `skill_id` exactly (the loader does `getattr(module, skill_id)`), and `skill_id` rejects hyphens — so skill folder, `skill_id` and function name are the same underscore-only name. Platform-side creation paths sanitize names to `[a-z0-9_]`; use underscores everywhere and names round-trip.

## The CLI

The agent verbs (`up`, `down`, `brief`, `run`, `wait`, `logs`, `py`, `snap`, `open`, `say`, `look`) are in `references/agent-loop.md`. The project verbs:

```
zeon login / zeon auth status|logout   # the USER signs in; never read the token
zeon new project <name> [dir] [-t TEMPLATE]
zeon new skill|workflow|world|canvas <name>   # scaffold one item (canvas: also patches canvas_ui)
zeon new object <type>                 # copy a mesh-database type's URDF + object model into objects/<type>/
zeon clone <project> [dir]             # working tree from the cloud head (+ AGENTS.md/CLAUDE.md when absent)
zeon init                              # link this folder to a new cloud project and push it
zeon status / diff                     # review (status --json: head, remote_head, merge_in_progress, ...)
zeon commit -m MSG [paths]             # local snapshot
zeon push                              # send commits; refreshes a loaded instance
zeon pull                              # fetch the cloud head; fast-forward or write conflict markers
zeon sync                              # pull + merge + push in one step; refreshes a loaded instance
zeon log / checkout / reset            # history
zeon project list|show|rename|archive
zeon mesh-database list|show           # browse the catalog your org can see
zeon verify                            # not implemented yet (always exits 1)
```

- `zeon init` requires `skills/`, `workflows/` and `worlds/`, uses the **directory name** as the cloud project name, and refuses when `.zeon/` exists or the name is taken. It commits and pushes everything present.
- `zeon new object` hard-fails when the catalog has no entry for the type; it only writes files (push afterwards).
- Check `merge_in_progress` in `zeon status --json` before editing, or you edit files holding `<<<<<<<` markers.

## Sync rules

Work lives in three places: your **working tree**, the **cloud project** (canonical), and the **instance** that runs it (it loads the pushed version). One branch, `main`.

**What a commit takes.** Everything you author, plus:

- `data/` — the run artifacts (`captures/`, `logs/`, `api/`), except `data/runs/`;
- plan caches — `skills/<id>/.motion_plan_cache.pkl`;
- from each `executions/<run>/` folder only `run_log_<run>.jsonl` (older: `run_log.jsonl`) and `metadata.json`.

**What it leaves out** (it stays on the machine that wrote it): a run's state (checkpoints, hold and resume files, ledgers, world snapshots), `.runtime/`, `data/runs/`, `.zeon/`. A clone, pull or checkout never writes these either. If an older CLI pushed such a file, the next commit drops it and says so; the file stays on disk.

**The 64 MB per-file limit.** A file over 64 MB is left out of the commit and named (`left out <path> (<size>, over the 64 MB sync limit)`). If the parent commit had a version of it, the project keeps that version; otherwise it is not in the project. A pull never overwrites the local file and a checkout never deletes it. A 413 from the server names the file. Run artifacts the app pushes after a run skip oversized files the same way.

**What `zeon sync` does** (it mutates — know before running):

1. Commits any dirty working tree first ("local changes saved before sync").
2. Merges the cloud head. On text conflicts it writes `<<<<<<<` markers and sets merge-in-progress: resolve in-file, then `zeon sync --continue` (or `--abort`, which restores your local edits). Binary conflicts keep the cloud copy and save yours under `.zeon/backups/`.
3. Pushes with a check on the cloud ref. If the cloud moved meanwhile, the push says "the cloud has changed since your last sync — run `zeon sync`": sync again. Never force-reset to get past it.
4. Refreshes your instance when it has this project loaded ("instance refreshed").

**Pull before editing what the human may have changed.** The app saves to the cloud (a world saved in the World Builder, a workflow edited in the editor, run data pushed when a run the app watched ends). Run `zeon pull` (it refuses a dirty tree: commit first) or `zeon sync` before touching those files, and whenever a `notice:` says the cloud moved on. `scripts/cloud_delta.py` reports drift without changing anything.

**Artifacts.** `capture_image` writes under `data/captures/<execution_id>/`. `print_log` / `api_request` mirror into `data/logs|api/<execution_id>/` only with `save_to_project=True` (marked deprecated in favour of `export=True`, which uploads to a lab-owned bucket instead; it still works). Skills writing their own artifacts use `project_data_dir(...)`. Artifacts reach your disk with `zeon pull` / `zeon sync` once they are in the cloud.

Auth is a `zat_…` token in `.env` (or `~/.zeon/.env`). It is a secret: never read, print or commit it.
