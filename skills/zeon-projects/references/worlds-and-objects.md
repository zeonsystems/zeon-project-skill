# Worlds and objects

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
- `metadata.type` binds the instance to an object model: the project's `objects/<type>/` directory wins, then the global mesh database.
- `metadata.name` is the human name workflows reference in object inputs. Keep names unique and stable — renames break workflow input mappings and any skill that calls `get_object_pose("<name>")`.
- Some entries are synthetic primitives (workspace boundaries `x_min`…`z_max`, `table`, depth filters) — identified by a primitive `geometry.type` like `Cuboid` and empty `metadata`. Leave them alone. Real object instances have `geometry.type: "articulated"` with a `yaml_path`.
- Fields are read by direct key access at load time — a missing key is a `KeyError`, not a default. Don't drop keys from an entry you're editing, and don't invent values for `attachment_spec` — copy from an existing instance of the same type.

`worlds/<world_id>/live_state.yaml` — mutable per-object runtime state (tip-box counters, well calibration, pipette offsets). The platform reads *and writes* it; its schema, 1-based/well-label indexing conventions, and merge semantics are precise and unforgiving — read `references/live-state.md` before touching it or writing skills that use `get_world_state`/`set_world_state`.

## Objects — objects/<name>/

Two files, both named after the folder:

- `<name>.urdf` — XML kinematics/geometry. Root element `<robot name="<name>">`.
- `<name>.object_model.yaml` — anchors, parts, articulations:

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

Hard requirements: the `urdf` key, `articulations.default` (even with empty joints), and an anchor literally named `object`.

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
