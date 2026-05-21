# Flow: author a new object

An object is a folder under `objects/<name>/` containing a URDF (`<name>.urdf`) and a YAML (`<name>.object_model.yaml`). The skill scaffolds two placeholder files; the user (or a downstream populator) fills in kinematics, anchors, and articulations.

**Schemas**: `references/schema-object.md`, `references/naming-rules.md`.

## Required information (interview)

Ask one at a time:

1. **Object name** — pattern `^[a-z_][a-z0-9_-]{0,63}$`. Becomes `objects/<name>/`.
2. Tell the user the skill scaffolds placeholders (minimal URDF + minimal YAML with `anchors.object` only). They need to author the real URDF kinematics, OBJ/STL meshes, and additional anchor frames themselves. Confirm they want to proceed.
3. **Is the object articulated** (has movable joints)? If yes, list the joints they expect.
4. **Named anchors** (grasp points, hole positions, placement frames). At minimum the schema requires `object`; the user can add more later.
5. **Mesh file** (`.obj` / `.stl`)? The skill does NOT author meshes — the user supplies them separately and references them by relative filename in the URDF.

## Generation

1. Run `scripts/invoke_scaffold.py item object <name>`. Returns 2 files.
2. Decode the base64.
3. Write `objects/<name>/<name>.urdf` (minimal placeholder — `<robot name="<name>"><link name="base"/></robot>`).
4. Write `objects/<name>/<name>.object_model.yaml` (minimal placeholder — `urdf:`, `parts: {}`, `articulations.default.joints: {}`, `anchors.object` identity transform on `parent_link: base`).
5. Tell the user **what's still needed for the object to be usable**:
   - URDF: add `<link>`, `<joint>` definitions reflecting the real kinematics.
   - OBJ/STL files referenced from the URDF — the skill cannot author these.
   - YAML: populate `anchors` with `parent_link`, `description`, `link_T_anchor.xyz` (metres), `link_T_anchor.wxyz` (quaternion, w first) for each grasp point or named frame.
   - YAML: populate `articulations.<preset>.joints` with joint angles/positions for each preset (e.g. `open`, `closed`).
6. Offer to scaffold anchors interactively. For each anchor the user names, append an entry to the YAML:
   ```yaml
   <anchor_name>:
     parent_link: <link>
     description: "<text>"
     link_T_anchor:
       xyz:  [<x>, <y>, <z>]
       wxyz: [<w>, <x>, <y>, <z>]
   ```

## Validation

1. URDF parses as XML.
2. `<robot name="<name>">` matches the folder name.
3. YAML parses.
4. YAML has `urdf:`, `articulations.default`, `anchors.object`.
5. Every anchor's `parent_link` matches a `<link>` in the URDF.
6. Every `articulations.<preset>.joints` key matches an actuated `<joint>` in the URDF.
7. `scripts/validate_project.py` confirms structural integrity.

## Cross-reference checks

- If a world's `world_state.json` references this object (`geometry.yaml_path` ending in `/objects/<name>/<name>.object_model.yaml`), the rename of this object will require updating that world too. Use `refactor-flow.md` for renames.

## Common mistakes

- Adding `parts:` entries that reference link names not in the URDF.
- Quaternion in the wrong order. Use `[w, x, y, z]`.
- `parent_link: world` when the URDF only has `<link name="base"/>`. The two must match.
- Asking the skill to generate `.obj` / `.stl` files. → Decline; explain that meshes must be authored externally.

## After writing

- Re-run `scripts/validate_project.py`.
- Ask the user: "Want to register this object in a world?" → If yes, route to `authoring-world.md` "Modify an existing world" or `develop-mode.md` Modify.
