# Worlds and objects

> Hosted docs: [Worlds and objects](https://readme.zeonsystems.app/docs/worlds-and-objects.md) · [The world state file](https://readme.zeonsystems.app/docs/worlds-world-state-json.md) · [The object model file](https://readme.zeonsystems.app/docs/objects-object-model-yaml.md) · [Anchors](https://readme.zeonsystems.app/docs/anchors.md)

**Objects** are physical things (plates, instruments, holders) defined once per type.
**Worlds** place *instances* of them. Skills reach objects through named **anchors**,
never raw coordinates; that is what makes a skill work in another world.

## Worlds: worlds/<world_id>/

A world directory is in one of two formats. Check `world_state.json` first:

**Saved world** (`"format": "zeon_world_state/2"`): what the World Builder and the
platform write.

```
worlds/<world_id>/
├── world.world              # the world itself (poses, parents, joints); what loads
├── world.world.engine.json  # per instance: type, metadata, seat
├── world_state.json         # a manifest DERIVED from the two above; never read back
└── live_state.yaml          # run-time state (references/live-state.md)
```

Editing `world_state.json` of a saved world changes nothing. Move, add or seat
objects in the World Builder (or from the instance REPL), then pull the result.

**Old layout** (`world_state.json` with `"version"` and per-instance `mount` blocks,
as the starter project ships): the platform only reads it. It is imported when the
world loads; the platform never writes it, so saving the world from the app needs a
new world name. You may edit it by hand; copy an existing instance as the template:

```json
"wellplate_stand_1": {
  "geometry": {"type": "articulated", "yaml_path": "objects/wellplate_stand/wellplate_stand.object_model.yaml"},
  "mount": {"type": "FixedMount", "world_P_body_fixed": {"xyz": [0.467, -0.392, 0.0], "wxyz": [1.0, 0.0, 0.0, 0.0], "stamp_s": null}},
  "enabled": true, "filter_from_depth": true, "collide_in_planner": true,
  "attachment_spec": {"fit_type": "voxel_volume_sample_surface", "surface_sphere_radius": 0.001, "voxelize_method": "ray", "n_spheres": 32},
  "metadata": {"name": "wellplate_stand_1", "type": "wellplate_stand"},
  "joint_config": {}
}
```

- The key is the **instance id**: what skills, workflow object inputs and
  `live_state.yaml` use. Plain readable ids (`wellplate_stand_1`) are the norm; a
  skill's `spawn` makes `<type>_<n>`.
- `mount.world_P_body_fixed` is the world pose of the object's **`object` anchor**;
  `xyz` in metres, `wxyz` scalar-first.
- `joint_config` sets an articulated object's joints (`{"lid_joint": 0.0}`).
- `Cuboid` entries (tables) become box primitives. Workspace-boundary walls
  (`x_min` ... `z_max`) are skipped.
- The type is `metadata.type`, else the folder after `objects/` or
  `mesh_database/` in `yaml_path`, else that file's stem.

**Type resolution, both formats:** the project's `objects/<type>/` first, then the
shared mesh database. A project copy is optional: an instance whose type is only in
the mesh database loads normally. A type found in neither place is **not loaded**:
the rest of the world loads and the instance is reported as missing (`zeon up
--json` lists it under `world_missing`). Check a type with `scripts/mesh_object_info.py
<type>`. Materialize (`zeon new object <type>`) only to edit its anchors or model.

## Objects: objects/<type>/

```
objects/<type>/
├── <type>.urdf                 # kinematics; meshes resolve from the mesh database
├── <type>.object_model.yaml    # parts, articulations, anchors (strict schema)
├── motions.yaml                # optional: recorded motions (references/motions.md)
├── tags.yaml                   # optional: the tags of the type's one tagged unit
└── units/<handle>/tags.yaml    # optional: one per physical tagged unit
```

`<type>.object_model.yaml`:

```yaml
urdf: wellplate_96_flatbottom.urdf
profile:
  template: null            # the kind: null (plain), arm, gripper, camera
parts:
  body: {links: [body], description: 96-well plate}
articulations:
  default: {description: Static labware, joints: {}}
anchors:
  object:                   # required: the object's frame
    parent_link: body
    description: Placement frame
    link_T_anchor: {xyz: [0.06388, -0.042735, 0.0], wxyz: [0.707107, 0.0, 0.0, -0.707107]}
  grasp_short:
    parent_link: body
    description: "Grip the short side | grasp: width 0.075 m, gripper_variant wellplate"
    link_T_anchor: {xyz: [0.0002, 0.0004, -0.0037], wxyz: [0.0, 0.707107, -0.707107, 0.0]}
```

**The loader is strict; a violation refuses the object** (and its instances do not
load):

- Top-level keys only `urdf`, `profile`, `parts`, `articulations`, `anchors`,
  `spherization`. App-specific data goes under `profile:`. `profile.template` is
  required.
- An anchor has only `parent_link`, `description`, `link_T_anchor`. The old `grasp:`,
  `viewpoint:`, `sampling:`, `prior_weights:` blocks are refused.
- An anchor named `object` is required. With moving joints in the URDF,
  `articulations.default` must list exactly those joints.
- No `tag_<id>` anchors: tags live in a unit's `tags.yaml`.
- No `motions:` key: motions live in `motions.yaml`.

`scripts/validate.py` checks all of these.

### Grasps live in the anchor description

A grasp anchor's description ends with one segment
`grasp: width <w> m[, standoff <s> m][, gripper_variant <variant>]`, after ` | `.
`width` is required; a missing `standoff` is 0.05 m; a missing `gripper_variant`
means the stock gripper. A second or malformed segment raises when a skill reads the
anchor. `anchor(obj, name)` returns it as `.width`, `.standoff`, `.gripper_variant`.

### The object frame is the `object` anchor

Every object pose the platform stores or returns is the pose of the anchor named
`object`: an instance's placement, `get_object_pose`, `set_object_pose(obj, pose)`
(default `anchor="object"`), the result of a localization. On real objects that
anchor is often centimetres away from the URDF/mesh origin and rotated. So:

- Never read an anchor's `link_T_anchor` as its offset from the object's pose. Call
  `anchor(obj, name).pose` (world) instead.
- To place an object, give the `object` anchor's pose, or place by another anchor:
  `set_object_pose(obj, pose, anchor="bottom_center")`.
- Moving the `object` anchor moves every existing placement of that object (they
  are poses of that frame). Treat it as fixed once the object is in use.

### Anchor conventions

Nothing checks these at run time; a wrong +z approaches from the wrong side.

- Grasp (TCP) anchors: +z points along the approach, into the object; the
  pre-approach backs off along -z.
- Seat anchors (`top_center`, `slot_<n>`): where an occupant's `bottom_center`
  lands; +z up.
- Camera anchors: +z is the optical axis.

When you add or edit an anchor, state which convention you applied and compare it
with a sibling anchor on the same object.

### Tags (fiducials) are per physical unit

A unit's tags are a measured export (`format: tag_calibration/3`): `tags.yaml`
beside the model for a type's only unit, or `units/<handle>/tags.yaml` (handle
`[a-z][a-z0-9_-]*`) for several. A world instance binds a unit through
`metadata.tag_collection`; `localize_object_tags(obj, collection="<handle>")`
overrides it. Only the `DICT_APRILTAG_36h11` family is detected. These files come
from the platform's tag calibration; never hand-write one. A leftover
`tag_collections/` folder is no longer read.

## Getting real objects

Real geometry comes from the mesh database, never from hand-written files:
`zeon new object <type>` (or adding the object in the World Builder) materializes
the URDF and object model into `objects/<type>/`. `zeon mesh-database list/show`
browses the catalog. An item without both `<type>.urdf` and
`<type>.object_model.yaml` cannot be materialized. A hand-written object is a
placeholder frame with no geometry. Edits to a materialized object's YAML stay in
the project.
