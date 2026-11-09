from protocol_schema import SkillObject

from .modules import (
    anchor,
    attach,
    contact,
    move_arm,
    move_arm_js,
    move_relative,
    print_log,
    release,
    resolve,
    set_gripper,
)

ARM = "left"
HOME = [0.0, -0.6, -1.0, 0.0, 1.6, 0.0]  # joint1..joint6, rad
OPEN_M = 0.085


def demo_skill(target_x: float = 0.1, plate: SkillObject = {"object_ref": "tipbox_10ul_1"}):
    """Fixture skill used by validator regression tests."""
    print_log("demo_skill start")
    move_arm_js(ARM, HOME, speed=0.5)
    # tipbox_grey has no objects/ copy in this project: it loads from the mesh
    # database, so neither this call nor the world instance may be flagged.
    grasp = anchor("tipbox_10ul_1", "grasp")
    anchor("plate_from_workflow_input", "grasp")
    plate_id = resolve(plate)
    set_gripper(ARM, OPEN_M)
    move_arm(ARM, grasp.preapproach(target_x))
    with contact(ARM, plate_id):
        move_arm(ARM, grasp, straight_line=True, tcp_speed=0.03)
        set_gripper(ARM, grasp.width)
        attach(ARM, plate_id, snap_anchor="grasp")
        move_relative(ARM, (0.0, 0.0, 0.05), tcp_speed=0.05)
        release(ARM, width=OPEN_M)
    move_arm_js("left_arm", HOME)
    return {"success": True}
