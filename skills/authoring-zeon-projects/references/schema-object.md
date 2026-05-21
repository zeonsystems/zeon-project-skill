# Object schema

A project-bound object is a folder under `objects/<name>/`:

```
objects/<name>/
├── <name>.urdf                  # required — kinematic structure
└── <name>.object_model.yaml     # required — anchors, articulations, parts
```

Mesh files (`.obj`, `.stl`) live in the mesh database, **not** in the project. Don't author them with the skill.

Validated at load time by `zeon_robotics.load_object_model()` (proprietary). The scaffolder's minimum is whatever passes that schema; see `everything-prototype-containers/services/execution/src/execution/mesh_database/tests/test_scaffold_compat.py` for the regression test that ensures the empty stubs load.

---

## `<name>.urdf`

URDF XML describing the object's kinematic structure. The minimum the schema requires is a single fixed link:

```xml
<?xml version='1.0' encoding='utf-8'?>
<robot name="<name>">
  <link name="base" />
</robot>
```

This is the byte-identical output of `_scaffold.py:303-308` (`_OBJECT_URDF`). The `<name>` in `<robot name="...">` should match the folder name.

For a real (non-placeholder) object, add geometry references:

```xml
<?xml version='1.0' encoding='utf-8'?>
<robot name="<name>">
  <link name="world" />
  <joint name="world_joint" type="fixed">
    <parent link="world" />
    <child link="body" />
    <origin rpy="0 0 0" xyz="0 0 0" />
  </joint>
  <link name="body">
    <visual>
      <geometry><mesh filename="<name>.obj" /></geometry>
    </visual>
    <collision>
      <geometry><mesh filename="<name>.obj" /></geometry>
    </collision>
  </link>
</robot>
```

For an articulated object (lid, drawer, etc.), add `revolute` / `prismatic` joints between named links. The skill does NOT auto-generate kinematics — ask the user, or leave the placeholder for them to fill.

URDF mesh paths use **relative** filenames (`<name>.obj`); the loader resolves them via the mesh database.

---

## `<name>.object_model.yaml`

Companion to the URDF. Describes anchors (named frames you can grasp / place at), articulations (named joint presets), and parts (named geometry components).

### Required fields

| Field | Type | Notes |
|---|---|---|
| `urdf` | string | Filename of the companion URDF, relative to this YAML. Always `<name>.urdf`. |
| `articulations.default` | object | Must exist with at least an empty `joints: {}` (matches a URDF with no actuated joints). |
| `anchors.object` | object | **Required anchor.** Identity transform on the URDF's root link is fine; named other anchors must reference real URDF links. |

### Minimal valid YAML

Byte-identical to `_scaffold.py:310-328` (`_OBJECT_YAML`):

```yaml
# <name> object model — populated later
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
      xyz:  [0.0, 0.0, 0.0]
      wxyz: [1.0, 0.0, 0.0, 0.0]
```

Note `parent_link: base` — this matches the URDF's single `<link name="base"/>`. If the URDF uses a different root link name (e.g. `world`), change `parent_link` to match.

### Fully populated example (from `objects/coldblock_small/coldblock_small.object_model.yaml`)

```yaml
urdf: coldblock_small.urdf

articulations:
  default:
    description: "All joints at rest position"
    joints: {}

anchors:
  object:
    parent_link: world
    description: "Table placement frame, origin at corner"
    link_T_anchor:
      xyz:  [-0.058, 0.017, -0.020]
      wxyz: [0.587, 0.0, 0.0, 0.809]

  hole_1:
    parent_link: body
    description: "Tube hole 1"
    link_T_anchor:
      xyz:  [-0.040, 0.007, 0.020]
      wxyz: [0.986, 0.0, 0.0, 0.165]

  hole_2: { ... }
  # ...
  hole_15: { ... }
```

### `anchors.<name>` shape

| Key | Required | Notes |
|---|---|---|
| `parent_link` | yes | A `<link>` name from the companion URDF. |
| `description` | recommended | Human description. |
| `link_T_anchor.xyz` | yes | `[x, y, z]` in metres. |
| `link_T_anchor.wxyz` | yes | Quaternion `[w, x, y, z]` (note the order — w first). |
| `grasp.width` | no | Gripper width in metres when this anchor is a grasp pose. |
| `grasp.gripper_variant` | no | String matching a gripper variant the runtime knows about (e.g. `"wellplate"`). |

### `articulations.<name>` shape

| Key | Required | Notes |
|---|---|---|
| `description` | recommended | What this articulation preset means. |
| `joints` | yes (may be `{}`) | Map of `<joint_name>` → numeric value (radians for revolute, metres for prismatic). |

The `default` preset is required. Add others (e.g. `open`, `closed`) as the object needs.

### `parts` (optional)

Map of named mesh parts. Most objects use `parts: {}`. Used when a single URDF link aggregates multiple named meshes the runtime needs to reference.

---

## Validation the skill should run

1. URDF parses as XML (`xml.etree.ElementTree.parse` succeeds).
2. The XML root is `<robot name="<name>">`.
3. YAML parses (`yaml.safe_load` succeeds).
4. `urdf` field points at an existing sibling file.
5. `articulations.default` exists.
6. `anchors.object` exists.
7. Every anchor's `parent_link` matches a `<link name>` in the URDF.
8. Every articulation's `joints` map keys to existing actuated `<joint>` names in the URDF (or empty `{}` if no actuated joints).

## Common mistakes

- Adding `parts:` entries that reference link names not in the URDF.
- Listing joint values in `articulations.default.joints` when the URDF has no actuated joints (use `joints: {}`).
- Quaternion in the wrong order. The runtime expects `[w, x, y, z]`, NOT `[x, y, z, w]`.
- `parent_link: world` when the URDF's only link is `base` (or vice-versa). Match them.
- Setting `grasp.width` without `grasp.gripper_variant` (or vice-versa) when both are needed by the runtime planner.
- Authoring `.obj` / `.stl` mesh files. The skill must not. They live in the mesh database.
