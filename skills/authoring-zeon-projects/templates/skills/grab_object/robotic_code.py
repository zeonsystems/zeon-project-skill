import time

from protocol_schema import SkillObject

from execution.skill_editing.execution_functions import *


def grab_object(object: SkillObject):
    """Grasp a world object with the left arm gripper.

    Args:
        object: World object to pick up. Its centroid pose drives the
            approach trajectory, and its id is used to attach it to the
            TCP after the gripper closes.
    """
    pos = object.pose
    x, y, z = pos[0], pos[1], pos[2]

    # Step 1: Open gripper
    set_gripper(arm="left_arm", width_m=0.08)

    # Step 2: Move safely above centroid
    move_arm(
        arm="left_arm",
        position=[x, y, z + 0.2],
        orientation=[1.085106, -1.490891, 0.235473],
        safe=False,
        speed=300,
    )

    # Step 3: Move down to centroid
    move_arm(
        arm="left_arm",
        position=[x, y - 0.005, z + 0.01],
        orientation=[2.792021, -1.158447, -1.477334],
        safe=False,
        speed=100,
    )

    # Step 4: Close gripper and attach object to arm
    set_gripper(arm="left_arm", width_m=0.0)
    time.sleep(0.5)

    # Attach object to TCP and sync world
    attach_object_to_arm(object.id, arm="left_arm")

    # Step 5: Move up (object attached)
    move_arm(
        arm="left_arm",
        position=[x + 0.1, y + 0.1, z + 0.2],
        orientation=[2.792021, -1.158447, -1.477334],
        safe=False,
        speed=100,
    )

    # Step 6: Capture image with right arm
    capture_image(arm="right_arm", capture_name="grab_object_final")

    return {"success": True}
