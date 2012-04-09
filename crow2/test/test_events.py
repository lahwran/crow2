from crow2 import events
from crow2 import toposort
import pytest

class Counter(object):
    "a mutable counter"
    def __init__(self):
        self.count = 0
    def tick(self):
        self.count += 1

class TestHook(object):

    def test_simple(self):
        counter = Counter()
        hook = events.Hook()
        @hook
        def testfunc(event):
            counter.tick()
        hook.fire()
        assert counter.count == 1

    def test_simple_dependency(self):
        counter = Counter()
        hook = events.Hook()

        @hook
        def second(event):
            assert event.first_was_called
            event.second_was_called = True
            assert counter.count == 1
            counter.tick()

        @hook(before=second)
        def first(event):
            assert counter.count == 0
            counter.tick()
            event.first_was_called = True

        @hook(after=second)
        def third(event):
            assert counter.count == 2
            counter.tick()
            assert event.first_was_called
            assert event.second_was_called

        hook.fire()
        assert counter.count == 3

    def test_error_checking(self):
        with pytest.raises(events.DuplicateRegistrationError):
            hook = events.Hook()
            @hook
            @hook
            def stub():
                pass

        with pytest.raises(events.InvalidOrderRequirementsError):
            hook = events.Hook()
            @hook
            def firstfunc(event):
                pass
            @hook(tag="first", after=firstfunc)
            def stub():
                pass

        hook = events.Hook()
        @hook(after="dependency missing")
        def stub():
            pass
        with pytest.raises(events.DependencyMissingError):
            hook.fire()

    def test_tags(self):
        counter = Counter()
        hook = events.Hook(["early", "normal", "late"])

        @hook(tag="normal")
        def func_normal(event):
            assert event.first_was_called
            event.second_was_called = True
            assert counter.count == 1
            counter.tick()

        @hook(tag="early")
        def func_early(event):
            assert counter.count == 0
            counter.tick()
            event.first_was_called = True

        @hook(tag="late")
        def func_late(event):
            assert counter.count == 2
            counter.tick()
            assert event.first_was_called
            assert event.second_was_called
            assert event.somewhere_was_called

        @hook(before=":late", after="early")
        def func_somewhere(event):
            assert event.first_was_called
            event.somewhere_was_called = True
            assert counter.count > 0

        hook.fire()
        assert counter.count == 3

    def test_calldicts(self):
        hook = events.Hook()
        counter = Counter()

        @hook
        def check(event):
            assert event.foo
            assert event.bar
            event.baz = True

        originalcontext = {"foo": True}
        context = dict(originalcontext)
        result = hook.fire(context, bar=True)
        assert result.foo
        assert result.bar
        assert result.baz
        assert context == originalcontext

    def test_once(self):
        hook = events.Hook(["tag", "tag2"])
        counter = Counter()

        @hook.once(tag="tag")
        def callonce(event):
            counter.tick()
            assert counter.count == 1

        @hook.once(tag="tag2")
        def callsecond(event):
            counter.tick()
            assert counter.count == 2

        @hook.once(tag="temporary_tag")
        def forgetme(event):
            pass # tests tag garbage collection

        hook.fire()
        assert counter.count == 2
        hook.fire()
        assert counter.count == 2

        @hook.once(tag="tag")
        def tag_stub(event):
            pass

        @hook.once(tag="tag2")
        def tag2_stub(event):
            pass

        @hook.once(before="tag", after="tag2")
        def impossible_link(event):
            pass

        # if this fails, the tags were lost
        with pytest.raises(toposort.CyclicDependencyError):
            hook.fire()

        with pytest.raises(events.NotRegisteredError):
            hook.deregister(callonce)

    def test_dependency_lookup(self): #dependency lookups are very wrong
        hook = events.Hook()
        @hook
        def local_target(event):
            event.local_target_run = True

        @hook(after="local_target", before="hook_reference_target.target")
        def check_after(event):
            assert event.local_target_run
            event.check_from_remote_target = True

        from .hook_reference_target import attach_to_hook
        attach_to_hook(hook, after="test_events.local_target")

        hook.fire()

def test_attrdict():
    d = events.AttrDict()
    d.blah = 1
    assert d.blah
    assert d == {"blah": 1}