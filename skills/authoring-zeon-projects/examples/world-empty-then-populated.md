# Example: world — empty vs populated

The skill emits the *empty* shape; the platform fills in the rest during a real scan. Showing both side by side so the agent knows what counts as scaffold-time content vs runtime-produced content.

## Empty world (skill writes this)

`worlds/empty_room/world_state.json`:

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
    "name": "empty_room",
    "description": "",
    "source": "manual"
  }
}
```

No `.bin`. No `.npz`. No workspace AABBs. No collision_cache. No blox parameters. Just enough for the loader to accept the file.

## Populated world (after running a scan in the product)

`worlds/empty_room/world_state.json` (excerpt — full files run hundreds of lines):

```json
{
  "version": "2.0",
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
    "voxel_count": 0,
    "voxel_export_region": { "aabb_min": [-1.35, -1.81, -0.5], "aabb_max": [1.35, 1.09, 1.2] },
    "include_objects_in_voxels": false,
    "voxel_spec": null
  },
  "objects": {
    "x_min": {
      "geometry": { "class": "Cuboid", "kwargs": { "dims": [0.02, 2.9, 1.7] } },
      "mount": { "type": "FixedMount", "world_P_body_fixed": { "xyz": [-1.36, -0.36, 0.35], "wxyz": [1, 0, 0, 0], "stamp_s": null } },
      "enabled": true,
      "filter_from_depth": false,
      "collide_in_planner": true,
      "attachment_spec": { "fit_type": "VOXEL_VOLUME_SAMPLE_SURFACE", "surface_sphere_radius": 0.001, "voxelize_method": "ray" },
      "metadata": {}
    },
    "table": {
      "geometry": { "class": "Cuboid", "kwargs": { "dims": [0.68, 1.4, 0.05], "color": [0.6, 0.4, 0.2] } },
      "mount": { "type": "FixedMount", "world_P_body_fixed": { "xyz": [0.26, -0.36, -0.025], "wxyz": [1, 0, 0, 0], "stamp_s": null } },
      "enabled": true,
      "filter_from_depth": false,
      "collide_in_planner": true,
      "attachment_spec": { "fit_type": "VOXEL_VOLUME_SAMPLE_SURFACE", "surface_sphere_radius": 0.001, "voxelize_method": "ray" },
      "metadata": {}
    },
    "bowl_72bec4b9-7b3f-41af-af7a-6148f57cb0e2": {
      "geometry": { "class": "Mesh", "kwargs": { "file_path": "/app/data/mesh_database/bowl/bowl.obj" } },
      "mount": { "type": "FixedMount", "world_P_body_fixed": { "xyz": [0.30, -0.51, 0.00], "wxyz": [1, 0, 0, 0], "stamp_s": null } },
      "enabled": true,
      "filter_from_depth": true,
      "collide_in_planner": true,
      "attachment_spec": { "fit_type": "VOXEL_VOLUME_SAMPLE_SURFACE", "surface_sphere_radius": 0.001, "voxelize_method": "ray" },
      "metadata": { "name": "bowl" }
    }
  },
  "metadata": {
    "name": "empty_room",
    "description": "",
    "created_at": "2026-01-28T17:06:36.449780",
    "source": "manual"
  }
}
```

Plus on disk: `nvblox_map.bin` and `blox_voxels.npz` — produced by the scan.

## What the skill is responsible for

- **Write the empty shape** when creating a new world.
- **Read the populated shape** to enumerate objects (for refactor / consistency checks).
- **Add an object entry** to `objects: {}` when the user asks to register one in the world (using the populated-shape fields, but with values the user provides).

## What the skill MUST NOT do

- Author `nvblox_map.bin` or `blox_voxels.npz`.
- Invent `workspace_aabb_min/max` values.
- Invent `voxel_*` config.
- Set `enable_blox: true` without there being binary blox files on disk — they'll be referenced but missing.

When adding objects manually to a world, use this template per entry:

```json
"<type>_<uuid4>": {
  "geometry": { "type": "articulated", "yaml_path": "/app/storage/mesh_database/<type>/<type>.object_model.yaml" },
  "mount":    { "type": "FixedMount", "world_P_body_fixed": { "xyz": [x, y, z], "wxyz": [w, x, y, z], "stamp_s": null } },
  "enabled":            true,
  "filter_from_depth":  true,
  "collide_in_planner": true,
  "attachment_spec":    { "fit_type": "VOXEL_VOLUME_SAMPLE_SURFACE", "surface_sphere_radius": 0.001, "voxelize_method": "ray" },
  "metadata":           { "name": "<type>", "type": "<type>" },
  "joint_config":       {}
}
```

Generate the UUID4. Ask the user for the pose; don't invent one.
