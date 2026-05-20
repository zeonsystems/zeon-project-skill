import time

from protocol_schema import SkillObject

from execution.skill_editing.execution_functions import *


def drop_object(object: SkillObject, destination: SkillObject):
    """Release the grasped object above the destination and back away.

    Args:
        object: World object currently attached to the TCP. Its id is
            used to detach it from the arm after release.
        destination: World object whose centroid pose is the drop target.
    """
    pos = destination.pose
    x, y, z = pos[0], pos[1], pos[2]

    move_arm(
        arm="left_arm",
        position=[x, y, z + 0.15],
        orientation=[2.792021, -1.158447, -1.477334],
        safe=False,
        speed=100,
    )

    # Step 2: Detach object from arm and sync world
    detach_object_from_arm(object.id)

    # Step 3: Open gripper
    set_gripper(arm="left_arm", width_m=0.08)
    time.sleep(2)

    # Step 4: Move back up
    move_arm(
        arm="left_arm",
        position=[x, y, z + 0.2],
        orientation=[1.085106, -1.490891, 0.235473],
        safe=False,
        speed=100,
    )

    # Step 5: Close gripper
    set_gripper(arm="left_arm", width_m=0.0)

    # Step 6: Capture image with right arm for testing
    capture_image(arm="right_arm", capture_name="drop_object_final")

    return {"success": True}
