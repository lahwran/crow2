
def attach_to_hook(hook, *args, **keywords):
    @hook(*args, **keywords)
    def target(event):
        assert event.check_from_remote_target
    return target
