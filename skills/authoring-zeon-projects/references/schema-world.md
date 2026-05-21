# World schema

A world is a folder under `worlds/<world_name>/` describing a physical scene the robot can run in.

```
worlds/<world_name>/
├── world_state.json    # required — scene description
├── nvblox_map.bin      # OPTIONAL — runtime artefact, never authored by hand
└── blox_voxels.npz     # OPTIONAL — runtime artefact, never authored by hand
```

**Hard rule: the skill MUST NOT author `nvblox_map.bin` or `blox_voxels.npz`.** These are binary outputs produced by the platform's nvblox scanner during a real scan of a physical workspace. Creating fake ones produces invalid maps that break collision-aware planning. The skill creates and edits `world_state.json` only; the user generates the binary files by running a scan inside the product.

## `world_state.json`

The file is consumed by the proprietary `zeon_robotics.scene_understanding.world.World.update_objects_from_export()` function (see `services/execution/src/execution/hardware_manager/world_interface.py`). There is no public Pydantic model for it; the canonical structure is defined by the scaffolder + the example.

### Top-level shape

```json
{
  "version": "2.0",
  "config": { ... },
  "objects": { ... },
  "metadata": { ... }
}
```

### `version`

Always `"2.0"` for current files. If you encounter a different version, ask the user before rewriting.

### `config`

World-level settings. The scaffolder emits the minimum for a brand-new world; the populated examples carry more fields that the scanner adds.

Minimum (for a freshly-scaffolded empty world — `_scaffold.py:228-246`):

```json
"config": {
  "tensor_device": "cuda",
  "enable_blox": false,
  "create_workspace_boundaries": false
}
```

Fully populated (after a scan — see `templates/default/worlds/bowl_bottle/world_state.json`):

```json
"config": {
  "tensor_device": "cuda",
  "collision_cache": { "obb": 20, "mesh": 10 },
  "enable_blox": true,
  "blox_layer_name": "world",
  "blox_voxel_size": 0.01,
  "blox_integrator": "tsdf",
  "workspace_aabb_min": [-1.35, -1.81, -0.5],
  "workspace_aabb_max": [1.35,  1.09,  1.2],
  "create_workspace_boundaries": true,
  "map_saved": true,
  "mesh_saved": false,
  "voxel_count": 0,
  "voxel_export_region": { "aabb_min": [...], "aabb_max": [...] },
  "include_objects_in_voxels": false,
  "voxel_spec": null
}
```

| Field | Set by | Notes |
|---|---|---|
| `tensor_device` | scaffold | Always `"cuda"` unless user explicitly overrides. |
| `enable_blox` | scaffold (`false`) → scanner (`true` after first scan) | Indicates whether `.bin` / `.npz` exist. |
| `create_workspace_boundaries` | scaffold (`false`) → scanner (`true` after scan defines the workspace AABB) | Drives the workspace wall objects (x_min, x_max, y_min, y_max, z_min, z_max — see `objects` below). |
| `workspace_aabb_min/max` | scanner only | Don't author by hand. |
| `collision_cache`, `blox_*`, `voxel_*` | scanner only | Don't author by hand. |

**Rule of thumb**: for a freshly-scaffolded world, emit the minimum. Don't make up workspace AABBs or blox parameters. The platform's scanner fills them in.

### `objects`

Map of `<instance_id>` → object spec. Each instance ID is conventionally `<type>_<uuid4>` (e.g. `bowl_72bec4b9-7b3f-41af-af7a-6148f57cb0e2`), but the special workspace-boundary objects use unprefixed keys: `x_min`, `x_max`, `y_min`, `y_max`, `z_min`, `z_max`, `table`, `left_base_filter`, `right_base_filter`.

For an empty new world: `"objects": {}` is valid.

Each object entry:

```json
"<instance_id>": {
  "geometry": { ... },
  "mount":    { ... },
  "enabled":            true,
  "filter_from_depth":  <bool>,
  "collide_in_planner": <bool>,
  "attachment_spec":    { ... },
  "metadata":           { ... },
  "joint_config":       { ... }      // articulated objects only
}
```

#### `geometry`

Two shapes:

**Primitive (Cuboid for walls/table/etc.)**:
```json
"geometry": {
  "class": "Cuboid",
  "kwargs": {
    "dims":  [dx, dy, dz],
    "color": [r,  g,  b]    // optional
  }
}
```

**Mesh (simple object)**:
```json
"geometry": {
  "class": "Mesh",
  "kwargs": {
    "file_path": "/app/data/mesh_database/<name>/<name>.obj"
  }
}
```
The `file_path` is rewritten by `resolve_mesh_database_paths()` at load time so an absolute container path becomes a local-cache path. When authoring, write the absolute `/app/data/mesh_database/<name>/<name>.obj` form — that's what the loader expects and rewrites.

**Articulated (URDF-backed)**:
```json
"geometry": {
  "type": "articulated",
  "yaml_path": "/app/storage/mesh_database/<name>/<name>.object_model.yaml"
}
```
Note the different key: `type` (not `class`), and `yaml_path` instead of `kwargs.file_path`. Use this when the object has joints or anchors that the planner must respect (almost any project-bound object with anchors).

#### `mount`

How the object is anchored in the world. The scaffold's default mount is fixed:

```json
"mount": {
  "type": "FixedMount",
  "world_P_body_fixed": {
    "xyz":  [x, y, z],
    "wxyz": [w, x, y, z],
    "stamp_s": null
  }
}
```

Other mount types may exist (the codebase has not been surveyed for them); when you're not sure, use `FixedMount` with the user-supplied pose.

#### Booleans

| Field | Default | Meaning |
|---|---|---|
| `enabled` | `true` | Whether the object exists in the world. |
| `filter_from_depth` | varies | Whether the depth camera should mask this object (set `true` for the robot's own base filters; `false` for the table). |
| `collide_in_planner` | `true` | Include in collision checks. `false` for walls used only for depth filtering. |

#### `attachment_spec`

Surface-sampling parameters used when an object is grasped. The scaffold-default copy uses:
```json
"attachment_spec": {
  "fit_type": "VOXEL_VOLUME_SAMPLE_SURFACE",
  "surface_sphere_radius": 0.001,
  "voxelize_method": "ray"
}
```
Use this verbatim unless the user explicitly overrides.

#### `metadata`

Free-form. Common keys:
- `name` (string) — instance name; usually the object type.
- `type` (string) — object type (matches `objects/<type>/`).
- `location` (string) — sometimes set to the type as well.
- `calibration` (dict) — per-anchor x/y offsets, e.g. `{"A1": {"x": 0.001, "y": -0.002}, ...}`. Authored by the operator during a calibration run, not by the skill.

#### `joint_config` (articulated objects only)

```json
"joint_config": {
  "<joint_name>": <radians or meters>
}
```
For a lid joint: `{"lid_joint": 0.0}` etc. For static articulated objects, may be `{}`. Don't invent joint names — pull them from the object's `<name>.urdf` actuated joints.

### `metadata` (top-level)

```json
"metadata": {
  "name": "<world_name>",
  "description": "",
  "source": "manual"
}
```

Conventional values:
- `name` matches the folder name.
- `description` is free-form, may be empty.
- `source` is `"manual"` for user-authored worlds, `"scan"` for scanner-produced ones. Use `"manual"` for any world the skill creates.
- `created_at` (ISO-8601) is added by the platform when the world is first persisted; safe to set if you're producing the file from scratch.

## Minimal valid `world_state.json` (skill output for a brand-new empty world)

```json
{
  "version": "2.0",
  "config": {
    "tensor_device": "cuda",
    "enable_blox": false,
    "create_workspace_boundaries": false
  },
  "objects": {},
  "metadata": {
    "name": "<world_name>",
    "description": "",
    "source": "manual"
  }
}
```

This is exactly what `zeon_project_scaffold._scaffold._world_files()` emits.

## Cross-references the skill must check

- Every `geometry.yaml_path` should reference an object the user actually has — either in `objects/<name>/` for project-bound, or known in the mesh database for global. The skill can warn on dangling references but can't fully verify global mesh-database membership without network access.
- For an articulated object, the joints listed in `joint_config` should match `joints` in the corresponding `objects/<name>/<name>.urdf`.
- `metadata.name` and key prefix should align (e.g. `bowl_<uuid>` matches `metadata.name = "bowl"`).

## Common mistakes

- **Authoring `.bin` or `.npz` files.** Hard no. They must be produced by the product's scanner.
- Fabricating `workspace_aabb_min/max` or `voxel_*` fields. Leave them out for fresh worlds.
- Using relative paths for mesh `file_path`. Use the absolute `/app/data/mesh_database/...` form.
- Using `geometry.class = "Mesh"` with a `yaml_path` (mixing the two shapes). Pick one: primitive `class+kwargs.file_path`, articulated `type+yaml_path`.
- Confusing `objects` map keys with object type names. The keys are *instance* IDs (`<type>_<uuid>`); the type goes in `metadata.type`.
- Adding `joint_config` to non-articulated geometry. The field only applies when `geometry.type == "articulated"`.
