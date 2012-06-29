import functools

import pytest

from crow2.events.hooktree import HookTree
from crow2.events.hook import Hook
from crow2.events import exceptions
from crow2.test.util import Counter, should_never_run
import crow2.plugin
import crow2.main

class DummyTracker(object):
    def __init__(self, trackers, name):
        self.name = name
        self.loaded = False
        trackers.append(self)

    def load(self):
        self.loaded = True

def test_main(monkeypatch):
    # don't want plugins messing with it to make permanent changes
    hook = HookTree(start_lazy=True)

    trackers = []
    monkeypatch.setattr(crow2.plugin, "Tracker", functools.partial(DummyTracker, trackers))

    main = crow2.main.Main(hook, "core", ["pluginset", "pluginset2"])

    assert len(trackers) == 3
    core, pluginset, pluginset2 = trackers
    assert core.name == "core"
    assert pluginset.name == "pluginset"
    assert pluginset2.name == "pluginset2"
    assert all(tracker.loaded for tracker in trackers)

    mainloop_exitcodes = []

    @hook.init
    def init(event):
        assert event.main == main
        event.main.initialized = True

    @hook.mainloop
    def mainloop(event):
        assert event.main.initialized
        do_stuff(event)
        assert event.didnt_stop_immediately
        assert mainloop_exitcodes == [0]
        event.main.mainloop_ran = True

    def do_stuff(event):
        event.main.quit()
        event.didnt_stop_immediately = True

    @hook.stopmainloop
    def stopmainloop(event):
        mainloop_exitcodes.append(event.exitcode)

    @hook.deinit
    def deinit(event):
        assert event.main.mainloop_ran
        event.main.deinit_ran = True

    main.run()
    assert main.deinit_ran
    
class TestMainloopHook(object):
    def test_double_register(self):
        hook = crow2.main.MainloopHook()

        @hook
        def firstmainloop(event):
            should_never_run()

        with pytest.raises(exceptions.AlreadyRegisteredError):
            @hook
            def secondmainloop(event):
                should_never_run()

    def test_unregistered_fire(self):
        hook = crow2.main.MainloopHook()
        hook.fire()

    def test_mainloop_refire(self):
        hook = crow2.main.MainloopHook()

        counter = Counter()

        @hook
        def mainloop(event):
            with pytest.raises(crow2.main.AlreadyRunningError):
                hook.fire(event)
            counter.tick()

        hook.fire()
        assert counter.incremented(1)

    def test_exception_passes(self):
        hook = crow2.main.MainloopHook()

        class SentinelException(Exception):
            pass

        @hook
        def mainloop(event):
            raise SentinelException()

        with pytest.raises(SentinelException):
            hook.fire()

class DummyMain(object):
    def __init__(self, dummymains, hook, core, plugins):
        dummymains.append(self)
        self.hook = hook
        self.core = core
        self.plugins = plugins
        self.was_run = False

    def run(self):
        self.was_run = True


class TestScriptmain(object):
    def test_simple(self, monkeypatch):
        dummymains = []
        monkeypatch.setattr(crow2.main, "Main", functools.partial(DummyMain, dummymains))

        crow2.main.scriptmain(["core", "pluginset", "pluginset2"])
        assert dummymains[0].hook == crow2.hook
        assert dummymains[0].core == "core"
        assert dummymains[0].plugins == ["pluginset", "pluginset2"]
        assert dummymains[0].was_run

    def test_argparse_missing(self, monkeypatch):
        import sys
        monkeypatch.setitem(sys.modules, "argparse", None)

        with pytest.raises(ImportError):
            crow2.main.scriptmain([])

    def test_syargs(self, monkeypatch):
        import sys
        monkeypatch.setattr(sys, "argv", [sys.argv[0], "core", "pluginset", "pluginset2"])

        dummymains = []
        monkeypatch.setattr(crow2.main, "Main", functools.partial(DummyMain, dummymains))

        crow2.main.scriptmain()

        assert dummymains[0].hook == crow2.hook
        assert dummymains[0].core == "core"
        assert dummymains[0].plugins == ["pluginset", "pluginset2"]
        assert dummymains[0].was_run
