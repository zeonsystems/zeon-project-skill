# The hosted docs — what's there and how to read it

Base URL: **<https://readme.zeonsystems.app>**

- **Any page as clean markdown:** append `.md` to its URL —
  `https://readme.zeonsystems.app/docs/authoring-a-skill.md`. Fetch the `.md`
  form, not the HTML page.
- **Machine index of every page:** <https://readme.zeonsystems.app/llms.txt>
  (title + one-line excerpt + URL for each). Use it when this file doesn't
  name the page you want, or when a link here 404s — pages get renamed.

**When to fetch instead of reading a bundled reference.** The `references/` in
this skill are offline, load instantly, and are verified against platform
source — reach for them first for file formats and the robot API. Fetch a
hosted page when:

- the topic is **online only** (second table below) — the app UI, running
  workflows, hardware setup, accounts;
- you need more depth or worked examples than the reference carries;
- something suggests the platform has **moved past this skill** — a CLI flag,
  API name, or field that the references don't know about.

The two sources shouldn't contradict each other. If they do, trust the project
you are in first, then the `zeon` CLI, then check the hosted page's content
against `references/execution-functions.json` before acting — and tell the user
about the discrepancy.

## Covered offline — fetch only for more depth

| Topic | Bundled reference | Hosted page(s) |
|---|---|---|
| Orientation, vocabulary | *(SKILL.md)* | [Key concepts](https://readme.zeonsystems.app/docs/key-concepts.md), [Glossary](https://readme.zeonsystems.app/docs/glossary.md) |
| Project layout, `project.json` | `project-layout.md` | [The project manifest](https://readme.zeonsystems.app/docs/project-json.md), [File reference](https://readme.zeonsystems.app/docs/file-reference.md) |
| Dev loop, CLI, sync | `project-layout.md` | [The development loop](https://readme.zeonsystems.app/docs/the-development-loop.md), [CLI reference](https://readme.zeonsystems.app/docs/cli-reference.md), [zeon new](https://readme.zeonsystems.app/docs/zeon-new.md), [zeon project](https://readme.zeonsystems.app/docs/zeon-project.md), [Syncing your work](https://readme.zeonsystems.app/docs/syncing-your-work.md) |
| Skills — code + metadata | `skills.md` | [Skills](https://readme.zeonsystems.app/docs/skills.md), [Authoring a skill](https://readme.zeonsystems.app/docs/authoring-a-skill.md), [The skill metadata file](https://readme.zeonsystems.app/docs/skills-metadata-yaml.md) |
| The robot API | `execution-functions.json`, `skills.md` | [Skill runtime API](https://readme.zeonsystems.app/docs/skill-runtime-api.md) and its sub-pages: [arm + gripper](https://readme.zeonsystems.app/docs/arm-motion-and-the-gripper.md), [objects/anchors/world](https://readme.zeonsystems.app/docs/objects-anchors-and-the-world.md), [pipetting](https://readme.zeonsystems.app/docs/pipetting.md), [perception](https://readme.zeonsystems.app/docs/perception.md), [external APIs](https://readme.zeonsystems.app/docs/calling-an-external-api.md), [pausing/operator prompts](https://readme.zeonsystems.app/docs/pausing-and-operator-prompts.md), [state + logging](https://readme.zeonsystems.app/docs/skill-state-and-logging.md) |
| Motion idioms, transition poses | `patterns.md`, `transition-poses.md` | [Skill authoring patterns](https://readme.zeonsystems.app/docs/skill-authoring-patterns.md), [Arm motion and the gripper](https://readme.zeonsystems.app/docs/arm-motion-and-the-gripper.md) |
| Anchor snapping | `patterns.md` | [How anchor snapping works](https://readme.zeonsystems.app/docs/anchor-snapping.md) |
| Workflow graphs | `workflows.md` | [Workflows](https://readme.zeonsystems.app/docs/workflows.md), [Authoring a workflow](https://readme.zeonsystems.app/docs/authoring-a-workflow.md), [The workflow file](https://readme.zeonsystems.app/docs/workflows-json.md) |
| Executor semantics | `execution-model.md` | [Authoring a workflow](https://readme.zeonsystems.app/docs/authoring-a-workflow.md) — the reference goes deeper (verified against the executor) |
| Worlds and objects | `worlds-and-objects.md` | [Worlds and objects](https://readme.zeonsystems.app/docs/worlds-and-objects.md), [The world state file](https://readme.zeonsystems.app/docs/worlds-world-state-json.md), [The object model file](https://readme.zeonsystems.app/docs/objects-object-model-yaml.md), [Anchors](https://readme.zeonsystems.app/docs/anchors.md) |
| `live_state.yaml` | `live-state.md` | [Building a world](https://readme.zeonsystems.app/docs/building-a-world.md), [The world state file](https://readme.zeonsystems.app/docs/worlds-world-state-json.md) |
| Canvas run UIs | `canvas.md` | [Creating a canvas](https://readme.zeonsystems.app/docs/creating-a-canvas.md) |

## Online only — fetch when the question goes there

| Question | Hosted page |
|---|---|
| What is the platform / first project | [What is Zeon Systems](https://readme.zeonsystems.app/docs/what-is-zeon-systems.md), [Your first project](https://readme.zeonsystems.app/docs/your-first-project.md) |
| Installing the CLI, signing in | [Install the CLI](https://readme.zeonsystems.app/docs/install-the-cli.md), [Signing in](https://readme.zeonsystems.app/docs/signing-in.md), [CLI cheat sheet](https://readme.zeonsystems.app/docs/cli-cheat-sheet.md) |
| Running a workflow | [In the cloud sim](https://readme.zeonsystems.app/docs/running-a-workflow-in-the-cloud-sim.md), [On real hardware](https://readme.zeonsystems.app/docs/running-a-workflow-on-real-hardware.md) |
| The app UI | [The main app](https://readme.zeonsystems.app/docs/the-main-app.md) → [Home](https://readme.zeonsystems.app/docs/the-home-screen.md), [Workflow Editor](https://readme.zeonsystems.app/docs/the-workflow-editor.md), [World Builder](https://readme.zeonsystems.app/docs/the-world-builder.md), [Skills Editor](https://readme.zeonsystems.app/docs/the-skills-editor.md), [Object Database](https://readme.zeonsystems.app/docs/the-object-database.md), [Hardware Setup](https://readme.zeonsystems.app/docs/hardware-setup.md) |
| Sync went wrong / diverged | [How sync works](https://readme.zeonsystems.app/docs/how-sync-works.md), [zeon sync](https://readme.zeonsystems.app/docs/zeon-sync.md), [working-tree commands](https://readme.zeonsystems.app/docs/zeon-working-tree-commands.md), [Resolving a diverged project](https://readme.zeonsystems.app/docs/resolving-diverged-from-cloud.md) |
| Where object geometry comes from | [The mesh database](https://readme.zeonsystems.app/docs/the-mesh-database.md), [Adding an object](https://readme.zeonsystems.app/docs/adding-an-object.md), [zeon mesh-database](https://readme.zeonsystems.app/docs/zeon-mesh-database.md) |
| Editing in the browser | [The Web IDE](https://readme.zeonsystems.app/docs/the-web-ide.md) |
| Accounts, tokens, org members | [Your profile](https://readme.zeonsystems.app/docs/your-profile.md), [API tokens](https://readme.zeonsystems.app/docs/api-tokens.md), [Organization members](https://readme.zeonsystems.app/docs/organization-members.md), [zeon auth](https://readme.zeonsystems.app/docs/zeon-auth.md) |

Auth pages are for the **user** to act on — never read, print, or edit a token
yourself; ask them to run `zeon auth login`.

---

*This map covers all 57 published pages, verified 2026-07-24. `llms.txt` is
authoritative for what is live right now.*
