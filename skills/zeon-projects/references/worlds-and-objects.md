# Worlds and objects

> Hosted docs: [Worlds and objects](https://readme.zeonsystems.app/docs/worlds-and-objects.md) · [The world state file](https://readme.zeonsystems.app/docs/worlds-world-state-json.md) · [The object model file](https://readme.zeonsystems.app/docs/objects-object-model-yaml.md) · [Anchors](https://readme.zeonsystems.app/docs/anchors.md)

**Objects** are physical things (plates, instruments, fixtures) defined once per type. **Worlds** are saved scenes placing *instances* of those objects at poses. Skills target objects through named **anchors**, never raw coordinates — that's what makes skills reusable across worlds.

## Worlds — worlds/<world_id>/world_state.json

The World Builder app is the usual way to author scenes — poses are much easier to get right visually. Hand-authoring in JSON works too; copy an existing instance of the same type as your starting point.

Top level:

```json
{
  "version": "2.0",
  "config": {
    "tensor_device": "cuda",
    "enable_blox": false,
    "create_workspace_boundaries": false
  },
  "objects": { "<instance_key>": { … } },
  "metadata": { "name": "my_world", "description": "", "source": "manual" }
}
```

Both `"2.0"` and `"3.0"` schema versions exist in circulation; match whatever the project already uses. `objects` is a dict keyed by instance name — World-Builder-placed objects use the convention `<type>_<uuid4>` (e.g. `wellplate_pcr_76505b64-…`); follow it for new instances (`live_state.yaml` entries are keyed by the same string). An instance entry:

```json
{
  "geometry": {
    "type": "articulated",
    "yaml_path": "objects/wellplate_pcr/wellplate_pcr.object_model.yaml"
  },
  "mount": {
    "type": "FixedMount",
    "world_P_body_fixed": {
      "xyz": [0.35, -0.12, 0.02],
      "wxyz": [1, 0, 0, 0],
      "stamp_s": null
    }
  },
  "joint_config": {},
  "enabled": true,
  "filter_from_depth": false,
  "collide_in_planner": true,
  "attachment_spec": { … },
  "metadata": { "type": "wellplate_pcr", "name": "wellplate_pcr_parts_1" }
}
```

- Poses: `xyz` in metres, `wxyz` a **scalar-first** quaternion (`[1,0,0,0]` = identity).
- `metadata.type` binds the instance to an object model: the project's `objects/<type>/` directory wins, then the global mesh database. **A project copy is optional, provided the type exists in the mesh database with an object model** (check with `scripts/mesh_object_info.py <type>`). Such an instance loads normally even with no `objects/<type>/` folder: the loader resolves the model by name and re-points `yaml_path` itself, so a `yaml_path` naming a file that isn't in the project is fine. The name is the first present of `metadata.type`, then `metadata.name` (works only when it equals the type), then, with no metadata at all, the `objects/<name>/` segment of `yaml_path`; a later one is never tried when an earlier one fails. A type found in neither the project nor the mesh database (a typo, a project-only object whose folder was deleted, a geometry-only catalog item) fails the **whole** world load. Don't materialize an object, or report its absence as a problem, just because the folder is missing — materialize only to edit its anchors or model. Read an unmaterialized object's anchors with `scripts/mesh_object_info.py <name>`.
- `mount.world_P_body_fixed` is the world pose of the object's **`object` anchor**, not of its URDF root or mesh origin (see [The object frame](#the-object-frame-is-the-object-anchor)).
- `metadata.name` is the human name workflows reference in object inputs. Keep names unique and stable — renames break workflow input mappings and any skill that calls `get_object_pose("<name>")`.
- Some entries are synthetic primitives (workspace boundaries `x_min`…`z_max`, `table`, depth filters) — identified by a primitive `geometry.type` like `Cuboid` and empty `metadata`. Leave them alone. Real object instances have `geometry.type: "articulated"` with a `yaml_path`.
- Fields are read by direct key access at load time — a missing key is a `KeyError`, not a default. Don't drop keys from an entry you're editing, and don't invent values for `attachment_spec` — copy from an existing instance of the same type.

`worlds/<world_id>/live_state.yaml` — mutable per-object runtime state (tip-box counters, well calibration, pipette offsets). The platform reads *and writes* it; its schema, 1-based/well-label indexing conventions, and merge semantics are precise and unforgiving — read `references/live-state.md` before touching it or writing skills that use `get_world_state`/`set_world_state`.

## Objects — objects/<name>/

Two files, both named after the folder:

- `<name>.urdf` — XML kinematics/geometry. Root element `<robot name="<name>">`.
- `<name>.object_model.yaml` — anchors, parts, articulations, motions:

```yaml
urdf: <name>.urdf

parts: {}

articulations:
  default:
    description: "Empty default articulation"
    joints: {}

anchors:
  object:
    parent_link: base
    description: "Object reference frame"
    link_T_anchor:
      xyz: [0.0, 0.0, 0.0]
      wxyz: [1.0, 0.0, 0.0, 0.0]
```

Hard requirements: the `urdf` key, `articulations.default` (even with empty joints), and an anchor literally named `object`. `parts` and `motions` are optional.

### The object frame is the `object` anchor

The `object` anchor **is** the object's frame. At load the platform re-roots the URDF so that frame becomes the object's origin. Keep it on the root link (the annotation editor requires this): the re-rooting is evaluated once at the `default` articulation, so an `object` anchor on a moving link would not follow it. Everything below is expressed in it:

- **Placement.** Absent a workflow-input offset, an instance's `world_P_body_fixed` in `world_state.json`, `get_object_pose(...)`, the rotation and `origin_*` fields of `SkillObject.pose`, `snap_object_to_world_pose(...)`, and the pose a localization solve writes are all the world pose of the `object` anchor.
- **Anchors.** `load_object_anchor` returns `world_P_object ∘ object_T_anchor`. An anchor is *stored* as `link_T_anchor` on its `parent_link`, but its offset from the object is measured from the `object` anchor, not from that link's origin.

The URDF/mesh origin is just where the CAD export happened to put zero. On real objects the `object` anchor is commonly centimetres to tens of centimetres away from it, and rotated (one plate reader's sits 0.56 m below its mesh origin, turned almost 180°; a PCR plate's is 0.128 m along x and turned −90° about z). So:

- Never take an anchor's `link_T_anchor.xyz` as its offset from the object's pose. Call `load_object_anchor`, or compose with the `object` anchor's own transform.
- To put an object somewhere, give the `object` anchor's target pose (or snap a named anchor with `snap_object_anchor_to_world_pose`). Don't place by the mesh's origin or bounding box.
- Moving the `object` anchor moves where every existing placement of that object appears, because those stored poses are poses of that frame. Treat it as fixed once an object is in use.

The scaffold placeholder puts `object` at identity on the root link, so for a hand-written placeholder the two frames coincide. Don't generalise that to real objects.

An optional top-level **`motions:`** map holds recorded tool paths — the sequence counterpart to an anchor, attached to a `parent_link` the same way. Never hand-write one; they are recorded by hand-guiding a real arm. Format and replay API: `references/motions.md`. Loader-fatal: a `parent_link` not in the URDF, fewer than two keyposes, keypose times that decrease or start below zero, a negative `gripper`.

### Tag collections — `objects/<name>/tag_collections/*.yaml`

Some objects carry a sidecar folder recording the fiducial tags stuck to **one physical copy**. The shared object model carries everything true of the *type*; each **tagged unit** adds only its own tags, so a lab can own three of something without three near-identical models. The unit's handle is the filename without extension (lowercase, leading letter, `[a-z0-9_-]`); a file whose name doesn't fit is ignored.

```yaml
schema: tag_collection/v1      # optional; if present must be exactly this
object: wellplate_holder       # required
family: apriltag_36h11         # optional; the ONLY accepted value
size_m: 0.020                  # optional, metres, positive (20 mm default)
tags:                          # required, at least one
  14:
    parent_link: body
    link_T_tag: { xyz: [0.031, 0.0, 0.048], wxyz: [0.5, -0.5, 0.5, 0.5] }
```

The collection is merged in at load time and never written back into the shared model. **An object uses one encoding or the other, never both** — older objects record tags inline as anchors named `tag_<id>`, and an object carrying both an inline `tag_<id>` anchor and a `tag_collections/` folder is *refused*, not merged. There is no tool for authoring a collection; one ships with an object or doesn't exist. Skills select a unit with `localize_object_tags(..., collection="<handle>")`.

**Get real objects from the mesh database, don't hand-author them**: `zeon new object <name>` (or adding the object in the World Builder) materializes the real URDF and object model into `objects/<name>/`. Use `zeon mesh-database list/show` to discover what's in the catalog; `download` mirrors an item's full manifest (including meshes) to a separate directory for inspection — don't point it at the project.

`zeon new object` contract: it needs the catalog item to contain **both** `<name>.urdf` and `<name>.object_model.yaml` — geometry-only items (just meshes) exist in the catalog and fail materialization with "missing required file(s)". It also aborts if `objects/<name>/` files already exist locally. To read an object's real anchors *before* materializing (or when deciding whether it's materializable at all), run `scripts/mesh_object_info.py <name>`. Hand-written object files are placeholders that render as an invisible frame. Mesh binaries themselves never live in the project — they resolve from the mesh database at load time. Edits to a materialized object's YAML (extra anchors, descriptions) stay project-local.

## Anchors

An anchor is a named frame rigidly attached to a URDF link:

```yaml
anchors:
  grasp_pose:
    parent_link: body
    description: "Where the gripper grabs"
    link_T_anchor:
      xyz: [0.0, 0.015, 0.09]
      wxyz: [0.707, 0.0, 0.707, 0.0]
```

Skills resolve them by name at runtime — `load_object_anchor("epipette_grey", "grasp_pose")` returns the pose against the object's live position. Adding a well-placed anchor to an object is usually the right way to make a skill work with it; hardcoding coordinates in skill code is usually the wrong way. An anchor may also carry a `grasp` block (`width`, `standoff`, `gripper_variant`) — skills should read grip geometry from it (`references/patterns.md`).

**Orientation conventions — nothing validates these at runtime, and a wrong +Z means the gripper approaches from the opposite side with no error message:**

- grasp/`tcp`-style anchors: **+Z points along the approach direction into the grasp**; pre-grasp retreats along −Z.
- `world`-frame anchors: +Z is up.
- `camera` anchors: +Z is the optical axis (OpenCV convention).
- `look_at` anchors: +Z is the outward viewing direction.

When authoring or editing an anchor, state which convention you applied and sanity-check it against a sibling anchor on the same object.
