# Example: world — empty vs populated

The skill emits the *empty* shape (single-file `world_state.json`, no binaries). The platform's scanner produces the populated shape (rich `objects` map + `nvblox_map.bin` + `blox_voxels.npz`).

## Empty world (skill writes this)

`worlds/<name>/world_state.json` — exactly what `_world_files()` in `zeon_project_scaffold._scaffold` emits, and what `scripts/invoke_scaffold.py item world <name>` writes:

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
    "name": "<name>",
    "description": "",
    "source": "manual"
  }
}
```

No `.bin`. No `.npz`. No workspace AABBs. No collision_cache. No blox parameters. Just enough for the loader to accept the file.

## Populated world (after running a scan in the product)

This is the real `bowl_bottle` world bundled with the scaffold and reproduced here from `templates/default/worlds/bowl_bottle/world_state.json`. It carries 6 workspace-boundary walls, a table, 2 base-filter cuboids, and 2 mesh objects (bowl, bottle):

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
    "workspace_aabb_max": [ 1.35,  1.09,  1.2],
    "create_workspace_boundaries": true,
    "map_saved": true,
    "mesh_saved": false,
    "voxel_count": 0,
    "voxel_export_region": { "aabb_min": [-1.35, -1.81, -0.5], "aabb_max": [1.35, 1.09, 1.2] },
    "include_objects_in_voxels": false,
    "voxel_spec": null
  },
  "objects": {
    "x_min": {
      "geometry": { "class": "Cuboid", "kwargs": { "dims": [0.02, 2.9, 1.7] } },
      "mount":    { "type": "FixedMount", "world_P_body_fixed": { "xyz": [-1.36, -0.36, 0.35], "wxyz": [1, 0, 0, 0], "stamp_s": null } },
      "enabled": true, "filter_from_depth": false, "collide_in_planner": true,
      "attachment_spec": { "fit_type": "VOXEL_VOLUME_SAMPLE_SURFACE", "surface_sphere_radius": 0.001, "voxelize_method": "ray" },
      "metadata": {}
    },
    "table": {
      "geometry": { "class": "Cuboid", "kwargs": { "dims": [0.68, 1.4, 0.05], "color": [0.6, 0.4, 0.2] } },
      "mount":    { "type": "FixedMount", "world_P_body_fixed": { "xyz": [0.26, -0.36, -0.025], "wxyz": [1, 0, 0, 0], "stamp_s": null } },
      "enabled": true, "filter_from_depth": false, "collide_in_planner": true,
      "attachment_spec": { "fit_type": "VOXEL_VOLUME_SAMPLE_SURFACE", "surface_sphere_radius": 0.001, "voxelize_method": "ray" },
      "metadata": {}
    },
    "bowl_72bec4b9-7b3f-41af-af7a-6148f57cb0e2": {
      "geometry": { "class": "Mesh", "kwargs": { "file_path": "/app/data/mesh_database/bowl/bowl.obj" } },
      "mount":    { "type": "FixedMount", "world_P_body_fixed": { "xyz": [0.30, -0.51, 0.00], "wxyz": [1, 0, 0, 0], "stamp_s": null } },
      "enabled": true, "filter_from_depth": true, "collide_in_planner": true,
      "attachment_spec": { "fit_type": "VOXEL_VOLUME_SAMPLE_SURFACE", "surface_sphere_radius": 0.001, "voxelize_method": "ray" },
      "metadata": { "name": "bowl" }
    },
    "bottle_35582ed6-be64-4e11-81d1-843e9bed5502": {
      "geometry": { "class": "Mesh", "kwargs": { "file_path": "/app/data/mesh_database/bottle/bottle.obj" } },
      "mount":    { "type": "FixedMount", "world_P_body_fixed": { "xyz": [0.28, -0.30, 0.02], "wxyz": [0.714, 0.700, 0.0, 0.0], "stamp_s": null } },
      "enabled": true, "filter_from_depth": true, "collide_in_planner": true,
      "attachment_spec": { "fit_type": "VOXEL_VOLUME_SAMPLE_SURFACE", "surface_sphere_radius": 0.001, "voxelize_method": "ray" },
      "metadata": { "name": "bottle" }
    }
    /* ... walls (x_max, y_min, y_max, z_min, z_max), left_base_filter, right_base_filter omitted for brevity */
  },
  "metadata": {
    "name": "bowl_bottle",
    "description": "",
    "created_at": "2026-01-28T17:06:36.449780",
    "source": "manual"
  }
}
```

Plus on disk: `nvblox_map.bin` and `blox_voxels.npz` — produced by the scanner. The scaffold ships a placeholder `blox_voxels.npz` (607 bytes); a real scan produces a much larger one.

For a more elaborate populated world, look at `golden-gate-assembly-mp6n1k2x/worlds/gg_world_14/world_state.json` — ~1980 lines, 40+ objects including articulated devices (`thermoeppendorf` with `joint_config`).

## What the skill is responsible for

- **Write the empty shape** when creating a new world.
- **Read the populated shape** to enumerate objects (for refactor / consistency checks).
- **Add an object entry** to `objects: {}` when the user asks to register one in the world — copy the full object-entry shape shown above (geometry / mount / enabled / filter_from_depth / collide_in_planner / attachment_spec / metadata).

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

Generate the UUID4 (`python3 -c "import uuid; print(uuid.uuid4())"`). Ask the user for the pose; don't invent one.
