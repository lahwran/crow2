"""
Target module for test_events.TestHook dependency reference testing
"""

def attach_to_hook(hook, *args, **keywords):
    "attach a target to provided hook, with provided args"
    @hook(*args, **keywords)
    def target(event):
        "Reference target"
        assert event.check_from_remote_target
    return target
