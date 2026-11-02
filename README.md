# zeon-project-skill

A Claude Code plugin for building things inside [Zeon](https://zeonsystems.app) robotics / lab-automation projects — robot skills, workflow graphs, worlds, objects, and canvas run UIs.

The skill is deliberately free-form: it gives the agent an accurate mental model of the platform, verified references (including the executor's actual runtime semantics), and deterministic tooling — then gets out of the way. No wizards, no fixed flows; describe what you want built and the agent builds it.

It also bridges to the hosted docs at **<https://readme.zeonsystems.app>**: `SKILL.md` ranks them as ground truth #4 (behind the project, the CLI, and the bundled references), every reference links the page covering the same topic, and `references/docs-index.md` maps topics to page URLs — including the things this skill deliberately doesn't bundle (the app UI, running workflows, sync recovery, accounts). Pages serve clean markdown by appending `.md`, and `/llms.txt` is the machine index.

## What's inside

```
skills/zeon-projects/
├── SKILL.md                      # orientation: anatomy, ground truth, tooling, safety
├── references/
│   ├── project-layout.md         # anatomy, project.json, naming, dev loop, CLI (+ --json surface)
│   ├── skills.md                 # robotic_code.py, metadata.yaml, the skill API v2, porting from v1
│   ├── workflows.md              # workflow JSON, validation rules, inputs, canvas_ui
│   ├── execution-model.md        # how the executor REALLY behaves (failure routing, loops, binding)
│   ├── patterns.md               # motion idioms: anchors, snapping, shared_state, retries, sim honesty
│   ├── motions.md                # recorded tool paths: replay API, tuning, the motions: block
│   ├── worlds-and-objects.md     # world_state.json, URDF + object model, tag collections, anchors
│   ├── canvas.md                 # sandboxed React run UIs, the full zeon host global
│   ├── docs-index.md             # map of the hosted docs: topic → page URL, offline vs. online-only
│   ├── skill-api.json            # vendored skill API v2 manifest (exact signatures, first doc lines)
│   └── execution-functions.json  # legacy v1 manifest (retired verbs marked), for old projects
└── scripts/
    ├── inspect.py                # whole-project map in one command
    ├── validate.py               # deterministic validator (mirrors runtime contracts)
    ├── cloud_delta.py            # read-only "has the cloud moved?" preflight
    ├── mesh_object_info.py       # read an object's real anchors from the mesh database
    └── dev/gen_function_manifest.py   # regenerate the API manifests from a platform checkout
```

Plus: `hooks/` (auto-validation hook config), `tests/` (fixture-based regression suite, run in CI), `evals/` (golden acceptance tasks for the skill itself).

## The validator

`scripts/validate.py` checks any project directory offline (stdlib-only; PyYAML optional). Beyond parse/naming/cross-reference checks, it mirrors the platform's **runtime** contracts, so failures that would otherwise surface mid-run on a physical robot become local errors:

- workflow node parameters vs. the skill function's actual signature (missing required parameter aborts a run; a typo'd key is silently dropped)
- imports and call sites vs. the vendored skill API manifest (v2 `execution.skill_api`; legacy v1 accepted with a warning) — unknown names, wrong kwargs, bad arity, deprecated names, by-name-only imports, calls to retired v1 motion verbs (they raise)
- literal `arm` arguments (v2: `left`/`right`; v1: anything but `left_arm`/`right_arm` silently moves the wrong physical arm)
- anchors referenced in skill code vs. object models; anchor `parent_link` vs. URDF links
- recorded `motions:` — `parent_link` in the URDF, at least two keyposes, non-decreasing keypose times, non-negative gripper widths
- `tag_collections/` sidecars — the `tag_collection/v1` schema, the `apriltag_36h11`-only rule, positive `size_m`, and the object-refusing conflict between inline `tag_<id>` anchors and a collections folder
- the executor's real expression grammar for conditional/loop nodes; collection-loop sources; identifier-safe loop ids; reserved state-key collisions
- catalog-fatal `metadata.yaml` rules (a broken file silently drops the skill from the catalog)
- `default`-edge-after-skill and `retry`-field traps; 16 MB blob cap; canvas sandbox rules

Exit 0 with no errors, 1 otherwise; `--json` for machine-readable output.

## Automatic validation (optional)

`hooks/hooks.json` ships a PostToolUse hook that runs the validator after every Write/Edit inside a Zeon project and feeds errors back to the agent. **Plugin-loaded PostToolUse command hooks are currently dropped by Claude Code** (upstream issue #34573), so to get this today, add the equivalent to your own `.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/zeon-project-skill/hooks/validate_changed_file.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

## Keeping it true as the platform evolves

- `references/skill-api.json` (v2) and `references/execution-functions.json` (legacy v1) record the date of the platform checkout they were generated from. Regenerate with `<platform venv python> skills/zeon-projects/scripts/dev/gen_function_manifest.py <platform-checkout> --write` (add `--api v1` for the legacy one); without the platform's environment it falls back to reading the sources statically (`--static`). Diff and commit.
- `tests/run_tests.py` (CI) validates the known-good fixtures (`valid_v2`: zero errors and warnings; `valid_min`: a legacy v1 project, zero errors) and a deliberately broken one (every planted defect must be reported).
- `evals/README.md` defines golden acceptance tasks for the skill; `evals/check.py` runs the deterministic parts.

## Install

```
/plugin marketplace add zeonsystems/zeon-project-skill
/plugin install zeon-project-skill@zeon
```

Restart Claude Code; the `zeon-projects` skill becomes discoverable. Then, in any Zeon project (or empty directory), ask for whatever you want to build:

- "Create a project that picks a plate from the cold block and seals it."
- "Add a skill that ejects the pipette tip into the waste bin."
- "Run tap_plate once per plate in a list the operator provides."
- "Why does my workflow fail validation?"
- "The workflow fails in sim — find out why and fix it." (with a cloud instance: the agent runs it with `zeon run`, reads `zeon logs`, fixes, and re-runs)

## Notes

- The agent never handles credentials: `zeon auth login` is run by you, and the skill treats the token in `.env` as off-limits (the bundled cloud tools keep it in memory and never print it).
- Skill code moves real robot arms. The skill reads grip geometry from anchors, flags anything that claims to disable safety behavior, treats clean sim runs as non-evidence of physical safety, and leaves hardware runs to you in the Zeon app.
- With a cloud instance, the agent verifies its work in the cloud simulator through the `zeon` CLI (`zeon py / run / wait / logs / snap`) and narrates into the 3D viewer (`zeon say / look / open`) so you can follow along. It works through the skill API only; REPL sessions are logged, and code that reaches past the skill API is refused with a hint the agent follows.
