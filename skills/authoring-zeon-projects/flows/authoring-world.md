# Flow: author a new world

A world is a folder under `worlds/<world_name>/` describing a physical scene. The skill creates an empty placeholder; the user generates the real spatial data (`.bin`, `.npz`, populated `world_state.json`) by running a scan inside the product.

**Schemas**: `references/schema-world.md`, `references/naming-rules.md`. Example: `examples/world-empty-then-populated.md`.

## Required information (interview)

Ask one at a time:

1. **World name** — snake_case, `^[a-z_][a-z0-9_-]{0,63}$`. Becomes `worlds/<name>/`.
2. **One-line description** — optional but recommended (goes into `metadata.description`).
3. **Will you scan this world live?** (yes / no)
   - If **yes**: the skill creates the empty placeholder. The user runs a scan in the product, which fills in `world_state.json` objects, generates `nvblox_map.bin` and `blox_voxels.npz`.
   - If **no**: ask what static objects to register. For each, collect: type (matching a `mesh_database` name or local `objects/<type>/`), pose `xyz` (metres), pose `wxyz` (quaternion, w-first), whether it's articulated.
4. **Should this become `project.json.active_world`?** Default yes if no `active_world` is set; otherwise ask.

## Generation — empty placeholder

1. Run `scripts/invoke_scaffold.py item world <name>`. The script returns `worlds/<name>/world_state.json` with the minimum config.
2. Decode the base64.
3. Overlay user-supplied `metadata.name`, `metadata.description` (the rest already matches the user).
4. Write `worlds/<name>/world_state.json` via `Write`.
5. Do NOT create `.bin` or `.npz` files. Do NOT add workspace AABBs or blox params.

If the user opts to set `project.json.active_world`, apply T2 ceremony (diff + confirmation) on `project.json`.

## Generation — registering static objects without a scan

When the user explicitly provides per-object pose data:

1. Start from the empty placeholder (above).
2. For each object the user wants, build an entry under `objects` (see schema):
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
3. Generate UUID4 keys (`python3 -c "import uuid; print(uuid.uuid4())"`).
4. For non-articulated objects, use `"geometry": { "class": "Mesh", "kwargs": { "file_path": "/app/data/mesh_database/<type>/<type>.obj" } }`.
5. For walls/floors (rare in user authoring), use `"geometry": { "class": "Cuboid", "kwargs": { "dims": [dx, dy, dz] } }` and the special keys `x_min`, `x_max`, `y_min`, `y_max`, `z_min`, `z_max`. Ask the user before adding these — they imply `create_workspace_boundaries: true` which requires the scanner to have run.
6. Each `<type>` must either:
   - Exist at `objects/<type>/` in this project, or
   - Be a known mesh-database row (the skill can't verify global membership without network).
   Warn the user if neither is provable.

## Modifying an existing world (T2)

Common changes:
- Add a new object to `objects` map.
- Update an object's `metadata.calibration` map.
- Remove an object the user no longer wants.
- Toggle `enabled` / `filter_from_depth` / `collide_in_planner`.

For each: Read current → propose change → show diff → wait for confirmation → Write/Edit → re-validate.

## Validation

1. `world_state.json` parses as JSON.
2. `version` is `"2.0"`.
3. `objects` is a dict.
4. Each object entry has `geometry`, `mount`, `enabled`.
5. `metadata.name` matches the folder name.
6. `scripts/validate_project.py` runs the cross-folder check (active_world resolves).

## Cross-reference checks

- Every `objects.<entry>.geometry.yaml_path` should resolve to either:
  - A local file under `objects/` (legacy direct path), or
  - A mesh-database name implied by `/app/storage/mesh_database/<name>/<name>.object_model.yaml`.
  Verifying the latter requires network access; warn but don't block.
- Every `objects.<entry>.geometry.kwargs.file_path` similarly.

## Common mistakes

- Authoring `.bin` or `.npz` files. **Never.** They come from the scanner.
- Setting `enable_blox: true` for an empty world. The blox files don't exist yet.
- Setting `workspace_aabb_min/max`. The scanner sets these.
- Confusing instance ID with type. Keys in `objects` are `<type>_<uuid>` (or special boundaries); `metadata.type` carries the type.
- Mixing `geometry.class` with `yaml_path`. Pick one shape per entry.
- Using relative paths in `file_path` or `yaml_path`. Use the absolute container path form (`/app/data/mesh_database/...`).

## After writing

- Re-run `scripts/validate_project.py`.
- Tell the user: "To get a runnable world, open the project in the Zeon product and run a scan; that produces the `.bin` / `.npz` files and fills in workspace boundaries and object poses."
- If `active_world` was set, mention that the project will boot to this world on next load.
