import pytest

import crow2.test.setup # pylint: disable = W0611
from crow2.test.util import Counter
from crow2.events.hook import Hook
from crow2.events import exceptions

class TestHook(object):
    """
    Test the Hook class
    """
    def test_simple(self):
        """
        Test that simple use of the Hook class works
        """
        counter = Counter()
        hook = Hook()
        @hook
        def testfunc(event):
            "call check"
            counter.tick()
        hook.fire()
        assert counter.count == 1

    def test_simple_dependency(self):
        """
        Test that simple three-in-a-row dependencies work
        """
        counter = Counter()
        hook = Hook()

        @hook
        def second(event):
            "handler with no dependencies"
            assert event.first_was_called
            event.second_was_called = True
            assert counter.count == 1
            counter.tick()

        @hook(before=second)
        def first(event):
            "handler which reverse-depends only on the second handler"
            assert counter.count == 0
            counter.tick()
            event.first_was_called = True

        @hook(after=second)
        def third(event):
            "handler which depends on the second handler"
            assert counter.count == 2
            counter.tick()
            assert event.first_was_called
            assert event.second_was_called

        hook.fire()
        assert counter.count == 3

    def test_error_checking(self):
        with pytest.raises(exceptions.DuplicateRegistrationError):
            hook = Hook()
            @hook
            @hook
            def stub():
                "registering to the same hook twice doesn't work"
                pass

        with pytest.raises(exceptions.InvalidOrderRequirementsError):
            hook = Hook()
            @hook
            def firstfunc(event):
                "a target function"
                pass
            @hook(tag="first", after=firstfunc)
            def stub():
                "function with nonsense order requirements"
                pass

        hook = Hook()
        @hook(after="dependency missing")
        def stub():
            "handler which depends on something which doesn't exist"
            pass
        with pytest.raises(exceptions.DependencyMissingError):
            hook.fire()

    def test_tags(self):
        counter = Counter()
        hook = Hook(["early", "normal", "late"])

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
        hook = Hook()
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
        hook = Hook(["tag", "tag2"])
        counter = Counter()

        def callonce(event):
            counter.tick()
            assert counter.count == 1
        hook.register_once(callonce, tag="tag")

        def callsecond(event):
            counter.tick()
            assert counter.count == 2
        hook.register_once(callsecond, tag="tag2")

        def forgetme(event):
            pass # tests tag garbage collection
        hook.register_once(forgetme, tag="temporary_tag")

        hook.fire()
        assert counter.count == 2
        hook.fire()
        assert counter.count == 2

        def tag_stub(event):
            pass
        hook.register_once(tag_stub, tag="tag")

        def tag2_stub(event):
            pass
        hook.register_once(tag2_stub, tag="tag2")

        def impossible_link(event):
            pass
        hook.register_once(impossible_link, before="tag", after="tag2")

        # if this fails, the tags were lost when there was nothing
        # pointed to them
        with pytest.raises(exceptions.CyclicDependencyError):
            hook.fire()

        with pytest.raises(exceptions.NotRegisteredError):
            hook.unregister(callonce)

    def test_dependency_lookup(self): #dependency lookups are very wrong
        hook = Hook()
        @hook
        def local_target(event):
            event.local_target_run = True

        @hook(after="local_target", before="hook_reference_target.target")
        def check_after(event):
            assert event.local_target_run
            event.check_from_remote_target = True

        from .hook_reference_target import attach_to_hook
        attach_to_hook(hook, after="test_hook.local_target")

        hook.fire()

    def test_get_name(self):
        hook = Hook()
        assert hook._get_name(TestHook) == "crow2.events.test.test_hook.TestHook"

        from crow2.events.test import hook_reference_target
        assert hook._get_name(hook_reference_target) == "crow2.events.test.hook_reference_target"

        assert hook._get_name(self.test_dependency_lookup) == "crow2.events.test.test_hook.TestHook.test_dependency_lookup"

        with pytest.raises(Exception):
            hook._get_name(5)

        class Immutable(object):
            "test to ensure caching does not cause any unexpected behavior"
            __slots__ = ()

        immutable_instance = Immutable()

        # NOTE: this is not the behavior people probably expect! will need documenting
        assert hook._get_name(Immutable) == "crow2.events.test.test_hook.Immutable"
        assert hook._get_name(Immutable) == "crow2.events.test.test_hook.Immutable"

    def test_unresolvable_object(self, capsys):
        hook = Hook()
        hook.register(tuple())

        out, err = capsys.readouterr()

        assert "warning" in out.lower()

        hook.unregister(tuple())

        out, err = capsys.readouterr()

        assert "warning" in out.lower()

    def test_error_logging(self, capsys):
        safe_hook = Hook(stop_exceptions=True)
        safe_counter = Counter()
    
        class TestErrorLoggingError(Exception):
            pass

        @safe_hook
        def raising_handler(event):
            event.before = True
            raise TestErrorLoggingError("derp")

        @safe_hook(after="raising_handler")
        def check_success(event):
            safe_counter.tick()
            assert event.before

        oldout, olderr = capsys.readouterr()
        # check that it works
        safe_hook.fire()
        assert safe_counter.count == 1
        out, err = capsys.readouterr() # test that the error was logged
        assert "TestErrorLoggingError" in out
        assert "derp" in out
        assert "raising_handler" in out

        unsafe_hook = Hook(stop_exceptions=False)
        unsafe_counter = Counter()

        @unsafe_hook
        def raising_handler_2(event):
            event.before = True
            raise TestErrorLoggingError("herp")

        @unsafe_hook(after="raising_handler_2")
        def should_never_run(event):
            assert event.before
            unsafe_counter.tick()

        with pytest.raises(TestErrorLoggingError):
            unsafe_hook.fire()
        assert unsafe_counter.count == 0

