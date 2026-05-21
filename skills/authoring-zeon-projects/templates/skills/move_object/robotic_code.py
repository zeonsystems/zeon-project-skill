from protocol_schema import SkillObject

from execution.skill_editing.execution_functions import *


def move_object(destination: SkillObject):
    """Move the currently-held object above the destination's centroid.

    Args:
        destination: World object whose centroid pose is the move target.
    """
    pos = destination.pose
    x, y, z = pos[0], pos[1], pos[2]

    # Step 1: Move to destination
    move_arm(
        arm="left_arm",
        position=[x, y, z + 0.2],
        orientation=[1.085106, -1.490891, 0.235473],
        safe=False,
        speed=200,
    )

    return {"success": True}
