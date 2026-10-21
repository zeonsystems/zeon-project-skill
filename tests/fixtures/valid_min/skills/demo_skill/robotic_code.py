from execution.execution_functions import load_object_anchor, move_arm, print_log


def demo_skill(target_x: float = 0.1):
    """Fixture skill used by validator regression tests."""
    print_log("demo_skill start")
    move_arm(arm="left_arm", position=[target_x, 0.0, 0.2],
             orientation=[0.0, 0.0, 0.0], speed=50, wait=True)
    # tipbox_grey has no objects/ copy in this project: it loads from the mesh
    # database, so neither this call nor the world instance may be flagged.
    load_object_anchor("tipbox_10ul_1", "grasp")
    load_object_anchor("plate_from_workflow_input", "grasp")
    return {"success": True}
