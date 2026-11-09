from execution.skill_api import move_arm, imaginary_teleport
from .modules import set_gripper


def bad_skill(skill_result, count):
    move_arm("left_hand", [0, 0, 0], speed=500, safe=False, turbo=True)
    move_arm(arm="left_arm")
    move_arm("right", [0.3, 0.0, 0.2], tcp_speed=0.05)
    set_gripper(arm="left_arm", width=0.02)
    invented_function_xyz(42)


def _read_state():
    from .modules import get_world_state
    return get_world_state("tipbox_10ul_1")
