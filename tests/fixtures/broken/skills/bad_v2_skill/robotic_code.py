from .modules import *  # noqa: F401,F403


def bad_v2_skill():
    a = anchor("bad_object", "no_such_anchor")
    move_arm("left", a, position=[0.1, 0.0, 0.2])
    move_arm("left_hand", a)
    place_object("bad_object", a.pose)
    print_log(deg(30))
    return {"success": True}
