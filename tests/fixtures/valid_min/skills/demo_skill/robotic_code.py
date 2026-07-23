from execution.execution_functions import move_arm, print_log


def demo_skill(target_x: float = 0.1):
    """Fixture skill used by validator regression tests."""
    print_log("demo_skill start")
    move_arm(arm="left_arm", position=[target_x, 0.0, 0.2],
             orientation=[0.0, 0.0, 0.0], speed=50, wait=True)
    return {"success": True}
