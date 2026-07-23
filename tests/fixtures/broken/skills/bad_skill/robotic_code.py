from execution.execution_functions import move_arm, imaginary_teleport
from .modules import set_gripper


def bad_skill(skill_result, count):
    move_arm(arm="left", position=[0, 0, 0], orientation=[0, 0, 0],
             speed=500, safe=False, turbo=True)
    move_arm(arm="left_arm")
    set_gripper(arm="left_arm", width_m=0.02)
    invented_function_xyz(42)
