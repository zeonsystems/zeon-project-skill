from .modules import play_object_motion, print_log


def legacy_skill():
    print_log("legacy_skill start")
    play_object_motion("shaker_1", "open_lid", arm="left_arm")
    return {"success": True}
