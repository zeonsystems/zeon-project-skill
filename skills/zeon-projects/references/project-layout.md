# Project layout, manifest, naming, and the dev loop

## Anatomy

```
project.json                     # manifest (below)
CLAUDE.md                        # per-project authoring notes — read first
skills/<skill_id>/
├── robotic_code.py              # the skill implementation (required)
├── metadata.yaml                # id/version/description/tags (required)
└── modules.py                   # optional shim: `from execution.execution_functions import *`
skills/utils.py                  # optional shared constants/helpers (arm poses etc.)
workflows/<workflow_id>.json     # one graph per file
worlds/<world_id>/
├── world_state.json             # the scene: object instances + poses
└── live_state.yaml              # mutable per-object state (tip counters, calibration)
objects/<name>/
├── <name>.urdf                  # kinematics/geometry references
└── <name>.object_model.yaml     # anchors, parts, articulations
canvas/<workflow_id>_screen.tsx  # optional custom run UI per workflow
inputs/<preset>.json             # optional input presets surfaced to canvases (see references/canvas.md)
data/                            # run artifacts, keyed per run by execution_id:
├── captures/<execution_id>/     #   camera snapshots (capture_image)
├── logs/<execution_id>/         #   run-log mirrors (print_log runlog lines)
├── api/<execution_id>/          #   saved api_request responses
└── runs/                        #   reserved, local-only — never synced, never authored
```

A fresh `zeon new project` seeds a runnable **pipette demo** (workflow `pipette_demo`, world `pipette_demo_world`, six skills — `epipette_grey_pick`/`_attach`/`_aspirate`/`_eject`, `epipette_tip_check`, `laser_read` — 17 objects, one canvas). Those files are reference material — copy their patterns into new files; don't overwrite them unless the user asks.

## project.json

```json
{
  "name": "My project",
  "description": "",
  "created_at": "2026-06-20T00:00:00.000Z",
  "updated_at": "2026-06-20T00:00:00.000Z",
  "archived": false,
  "active_workflow": "pipette_demo",
  "active_world": "pipette_demo_world"
}
```

- `name` is a free display string (≤128 chars, unique per user in the cloud). Item names are strict (below).
- `active_workflow` → must match an existing `workflows/<id>.json`; `active_world` → an existing `worlds/<id>/`. Either may be `null`.
- The editor opens `active_workflow`/`active_world` by default. Repointing them changes what runs by default — do it when the user's request calls for it (a new workflow they intend to run, an explicit switch), and say so when you do.
- Timestamps are ISO-8601 with milliseconds and a `Z` suffix.

## Naming rules

| What | Rule |
|---|---|
| Item folder / file names (skill, workflow, world, object, canvas) | `^[a-z_][a-z0-9_-]{0,63}$` |
| `skill_id`, `workflow_id`, node ids (in-file identifiers) | `^[a-z0-9_]+$` — use underscores, not hyphens |
| Workflow input names | `^[A-Za-z][A-Za-z0-9_]*$` |
| Versions (`version` fields) | semver `^\d+\.\d+\.\d+$`, e.g. `1.0.0` |

A skill's Python function name must equal the `skill_id` exactly (the loader does `getattr(module, skill_id)`), and `skill_id` rejects hyphens — so skill folder, `skill_id`, and function name must all be the same underscore-only name. Never use hyphens for skills; avoid them everywhere else too (platform-side creation paths sanitize to `[a-z0-9_]`).

## The dev loop and sync

Work lives in three places: the **local working tree**, the **cloud project** (canonical), and the user's **cloud instance / lab machine** (materialized for execution). `zeon sync` is what moves work between them.

```
zeon sync            # pull cloud changes, merge, push — the everyday step
zeon status / diff   # review before syncing
zeon commit          # snapshot locally without pushing
zeon log / checkout / reset   # history
zeon clone           # start a working tree from an existing cloud project
zeon init            # link an existing local directory to a new cloud project
zeon new project <name> [dir]  # create cloud project + local tree (pipette demo seed)
zeon new skill|workflow|world|canvas <name>   # scaffold one item
zeon new object <name>         # materialize an object from the mesh database
zeon project list|show|rename|archive
zeon mesh-database list|show|download        # browse the shared object catalog
zeon auth status               # check login (user runs `zeon auth login` themselves)
zeon verify                    # not yet implemented — always exits 1 (server-side verification is planned)
```

**Scripting the CLI** — `status`, `log`, `project list`, and `project show` take `--json`. `zeon status --json` gives `{head, remote_head, merge_in_progress, added, modified, deleted, unmerged}` — check `merge_in_progress` before editing, or you'll be editing files containing `<<<<<<<` conflict markers. `zeon project show --json` resolves a project name to its `project_id`.

**What `zeon sync` actually does** (it mutates — know before running):

1. Silently commits any dirty working tree first ("local changes saved before sync") — uncommitted WIP becomes a commit.
2. Merges the cloud head. On text conflicts it exits 1, writes `<<<<<<<` markers, and sets a merge-in-progress flag; resolve in-file, then `zeon sync --continue` (or `--abort`). Binary conflicts keep the cloud copy and save yours under `.zeon/backups/`.
3. Pushes with an If-Match on the ref — a concurrent cloud write means HTTP 412; just sync again (never force-reset to "fix" a 412).

To learn whether the cloud moved *without* mutating anything, use
`scripts/cloud_delta.py` — read-only, reports local/cloud head drift and
merge-in-progress state.

Other notes:

- One branch (`main`), single-user per project today.
- `zeon init` (link a hand-authored directory to a new cloud project) requires `skills/`, `workflows/`, and `worlds/` to exist, uses the **directory name** as the cloud project name, and refuses when `.zeon/` already exists or the name is taken. It commits and pushes everything present.
- Platform-side creation paths sanitize names to `[a-z0-9_]` (spaces/hyphens → underscores) — use underscores everywhere and local names will round-trip identically.
- Cloud blobs are capped at 16 MB (one oversized file breaks every future push of the project — validate.py checks); projects are text — binaries live in the mesh database.
- **Run artifacts sync themselves**: when a run ends, the app pushes `data/captures|logs|api/` to the cloud (oversized files are skipped, not fatal; `data/runs/` is excluded). Capturing into the project is **opt-in per call** — pass `save_to_project=True` on `capture_image`/`print_log`/`api_request` when the run record should keep the artifact. Skills writing their own artifacts use `project_data_dir(...)` rather than hand-building paths.
- Auth is a `zat_…` token in `.env` (or `~/.zeon/.env`). It is a secret: never read, print, or commit it.
- Workflows aren't run from the CLI: sim runs happen in the Zeon web app; hardware runs are started from the lab machine's local UI.
