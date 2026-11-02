from execution.execution_functions import load_object_anchor, move_arm_js, print_log


def demo_skill(target_x: float = 0.1):
    """Fixture skill used by validator regression tests: a legacy v1 skill
    (still loads; the validator warns on the v1 import)."""
    print_log("demo_skill start")
    move_arm_js(arm="left_arm", joint_angles=[target_x, 0.0, 0.2, 0.0, 0.0, 0.0], speed=0.5)
    # tipbox_grey has no objects/ copy in this project: it loads from the mesh
    # database, so neither this call nor the world instance may be flagged.
    load_object_anchor("tipbox_10ul_1", "grasp")
    load_object_anchor("plate_from_workflow_input", "grasp")
    return {"success": True}
