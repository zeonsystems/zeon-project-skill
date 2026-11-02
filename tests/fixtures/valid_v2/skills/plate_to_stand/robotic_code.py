from protocol_schema import SkillObject

from utils import ARM, CARRY_SPEED, DESCEND_TCP, HOME_JOINTS, POSTURE

from .modules import (
    WouldCollide,
    anchor,
    attach,
    contact,
    holding,
    move_arm,
    move_arm_js,
    move_relative,
    name_of,
    print_log,
    release,
    set_gripper,
)


def plate_to_stand(
    plate: SkillObject = {"object_ref": "plate_1"},
    stand: SkillObject = {"object_ref": "stand_1"},
    lift_m: float = 0.03,
):
    """Fixture skill (skill API v2): pick a plate by its grasp anchor and seat it on the stand.

    Args:
        plate: The plate to move.
        stand: The stand to put it on.
        lift_m: How far to lift straight up after the grasp (m).
    """
    print_log(runlog=True, runlog_type="step_start")
    if holding(ARM) is not None:
        raise RuntimeError(f"the {ARM} arm already holds {name_of(holding(ARM))}")
    g = anchor(plate, "grasp")
    set_gripper(ARM, (g.width or 0.08) + 0.02)
    move_arm(ARM, g.preapproach(), posture=POSTURE)
    with contact(ARM, plate):
        move_arm(ARM, g, straight_line=True, tcp_speed=DESCEND_TCP)
        set_gripper(ARM, g.width or 0.08)
        attach(ARM, plate, snap_anchor="grasp")
        move_relative(ARM, (0.0, 0.0, lift_m), tcp_speed=DESCEND_TCP)
    move_arm_js(ARM, HOME_JOINTS, speed=CARRY_SPEED)
    seat = anchor("stand_1", "top_center")
    try:
        move_arm(ARM, seat.preapproach(0.05))
    except WouldCollide:
        print_log("stand approach refused by the planner", runlog=True)
        raise
    with contact(ARM, stand):
        move_arm(ARM, seat, straight_line=True, tcp_speed=DESCEND_TCP)
        release(ARM, onto=(stand, "top_center"))
        move_relative(ARM, (0.0, 0.0, 0.05), tcp_speed=DESCEND_TCP)
    print_log(f"plate_to_stand: {name_of(plate)} on {name_of(stand)}", runlog=True)
    return {"success": True}
