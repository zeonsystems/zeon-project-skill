# Example: rich object with many anchors

This is the real `coldblock_small` object from the `golden-gate-assembly` project. It has 15 tube-hole anchors plus an `object` placement anchor — a good reference for what a fully-authored project-bound object looks like.

Source: `golden-gate-assembly-mp6n1k2x/objects/coldblock_small/`.

## `objects/coldblock_small/coldblock_small.urdf`

```xml
<?xml version='1.0' encoding='utf-8'?>
<robot name="coldblock_small">
  <link name="world" />
  <joint name="world_joint" type="fixed">
    <parent link="world" />
    <child link="body" />
    <origin rpy="0 0 0" xyz="0 0 0" />
  </joint>
  <link name="body">
    <visual>
      <geometry><mesh filename="coldblock_small.obj" /></geometry>
    </visual>
    <collision>
      <geometry><mesh filename="coldblock_small.obj" /></geometry>
    </collision>
  </link>
</robot>
```

Note: two links (`world` and `body`) connected by a fixed joint. The `world` link is the placement frame; `body` carries the mesh. This is richer than the scaffold's empty `<link name="base"/>` placeholder — production objects typically use the world+body pattern.

The `coldblock_small.obj` mesh lives **outside** the project (in the mesh database). The skill never authors `.obj` files.

## `objects/coldblock_small/coldblock_small.object_model.yaml` (excerpt)

```yaml
urdf: coldblock_small.urdf
articulations:
  default:
    description: All joints at rest position
    joints: {}
anchors:
  object:
    parent_link: world
    description: Table placement frame, origin at (+X, +Y, -Z) bbox corner
    link_T_anchor:
      xyz: [-0.058306, 0.0174318, -0.0198808]
      wxyz: [0.587185, 2.00645e-32, 2.71876e-32, 0.809453]
  hole_1:
    parent_link: body
    description: hole 1 xyz location
    link_T_anchor:
      xyz: [-0.0397037, 0.00730662, 0.020485]
      wxyz: [0.986324, -5.82899e-33, -3.07483e-34, 0.164815]
  hole_2:
    parent_link: body
    description: hole 2 xyz location
    link_T_anchor:
      xyz: [-0.0221931, 0.0124721, 0.020485]
      wxyz: [0.986324, -5.82899e-33, -3.07483e-34, 0.164815]
  # ... hole_3 through hole_15 follow the same shape
```

For an even richer object with grasp metadata, see `golden-gate-assembly-mp6n1k2x/objects/wellplate_pcr/wellplate_pcr.object_model.yaml`:

```yaml
anchors:
  grasp_short:
    parent_link: body
    description:
      grasp pose to grab the plate along the short sides, camera facing
      the +x direction of the object.
    link_T_anchor:
      xyz: [0.0639, 0.04274, -0.00553893]
      wxyz: [4.32978e-17, 0.707107, -0.707107, -4.32978e-17]
    grasp:
      width: 0.06
      gripper_variant: wellplate
  side_grab:
    parent_link: body
    description: Side grab the wellplate from the holder
    link_T_anchor:
      xyz: [0.06388, 0.0133059, 0.007677]
      wxyz: [-0.00220656, 0.00220656, 0.707103, 0.707103]
    grasp:
      width: 0.012
```

The `grasp` sub-key marks an anchor as a grasp pose; `width` is the gripper opening in metres and `gripper_variant` selects a planner-known gripper profile.

## Patterns to learn from

- **`object` anchor** is required (schema enforced). Use the URDF's root-ish link as `parent_link` — `world` here.
- **Hole/well anchors** all share the same orientation (`wxyz`) and differ only in `xyz` — that's normal for a planar grid of identical features.
- **Anchor names are free-form** as long as they're useful — `hole_1..hole_15` or `A1..H12` or `grasp_short` etc.
- **`grasp` metadata** on an anchor turns it into a planner-recognized grasp pose. Without `grasp`, the anchor is just a named frame the skill can use as a target.
- **Joints map to empty `{}`** when the object has no actuated joints (static object). For articulated objects like `thermoeppendorf`, `default.joints` would carry the at-rest values for each joint name in the URDF.

## What this object enables

Skills can call `load_object_anchor(object_id, "hole_3")` to get the pose of hole 3 on a `coldblock_small` instance; `move_arm` to that pose; aspirate / dispense / pick whatever lives there. The dense set of named anchors is what makes the project useful — each one is a target the workflow can address.

## What the skill should and shouldn't write

- **Skill writes**: this YAML structure with anchors the user names, URDF placeholder if no mesh yet, or the full URDF if the user supplies link/joint definitions.
- **Skill doesn't write**: `.obj` / `.stl` meshes (mesh database / external authoring), pose coordinates pulled from thin air (ask the user or leave a TODO).
