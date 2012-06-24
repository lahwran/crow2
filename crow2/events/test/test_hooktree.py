
from crow2.events.hooktree import HookTree, HookMultiplexer, CommandHook, InstanceHook
from crow2.events.hook import Hook, CancellableHook
from crow2.events.exceptions import AlreadyRegisteredError, NameResolutionError, NotRegisteredError
from crow2.test.util import Counter, should_never_run
import pytest

class TestHookTree(object):
    def test_createhook(self):
        hooktree = HookTree()
        hooktree.createhook("child_hook")
        assert isinstance(hooktree.child_hook, Hook)

    def test_createhook_customclass(self):
        hooktree = HookTree()
        hooktree.createhook("child_hook", hook_class=CancellableHook)
        assert isinstance(hooktree.child_hook, CancellableHook)

    def test_addhook(self):
        hooktree = HookTree()
        sentinel = object()
        hooktree.addhook("child_hook", sentinel)
        assert hooktree.child_hook is sentinel

    def test_createsub(self):
        hooktree = HookTree()
        hooktree.createsub("child_hooktree")
        assert isinstance(hooktree.child_hooktree, HookTree)
        assert hooktree.child_hooktree is not hooktree

    def test_instantiatehook(self):
        hooktree = HookTree()

        @hooktree.instantiatehook("child_hook")
        @hooktree.instantiatehook("child_hook_2", "herp", "derp", "whee", dink="donk")
        class WhackyHookSubclass(object):
            def __init__(self, *args, **keywords):
                self.args = args
                self.keywords = keywords

        assert isinstance(hooktree.child_hook, WhackyHookSubclass)
        assert hooktree.child_hook_2.args == ("herp", "derp", "whee")
        assert hooktree.child_hook_2.keywords == {"dink": "donk"}

    def test_missing_child(self):
        hooktree = HookTree()
        with pytest.raises(AttributeError):
            hooktree.derp

    def test_name(self):
        hooktree = HookTree(name="named_hooktree")

        assert "named_hooktree" in repr(hooktree)

    def test_hook_misplaced(self):
        hooktree = HookTree(name="named_hooktree")

        # TODO: this is actually a Hook test too
        hooktree.createhook("child", hook_class=Hook)

        assert "named_hooktree.child" in repr(hooktree.child)

    def test_name_collision(self):
        hooktree = HookTree()

        hooktree.createhook("child")

        with pytest.raises(AlreadyRegisteredError):
            hooktree.createhook("child")

class TestHookMultiplexerFiring(object):
    def test_missing_exception(self):
        hook = HookMultiplexer()

        with pytest.raises(NameResolutionError):
            hook.fire(name="")

    def test_preparer(self):
        hook = HookMultiplexer(preparer=Hook())
        counter1 = Counter()
        counter2 = Counter()
        counter_mapped = Counter()
        counter_preparer = Counter()

        @hook
        def derp(event):
            counter1.tick()

        @hook("herp")
        def herp(event):
            counter2.tick()

        mapping = {
                "dink": "herp",
                "donk": "derp"
        }

        @hook.preparer
        def prepare(event):
            if event.name in mapping:
                event.name = mapping[event.name]
                counter_mapped.tick()
            counter_preparer.tick()

        assert counter1.count == 0
        assert counter2.count == 0
        assert counter_preparer.count == 0
        assert counter_mapped.count == 0

        hook.fire(name="dink")

        assert counter1.count == 0
        assert counter2.count == 1
        assert counter_preparer.count == 1
        assert counter_mapped.count == 1

        hook.fire(name="donk")

        assert counter1.count == 1
        assert counter2.count == 1
        assert counter_preparer.count == 2
        assert counter_mapped.count == 2

        hook.fire(name="herp")
        
        assert counter1.count == 1
        assert counter2.count == 2
        assert counter_preparer.count == 3
        assert counter_mapped.count == 2

        hook.fire(name="derp")

        assert counter1.count == 2
        assert counter2.count == 2
        assert counter_preparer.count == 4
        assert counter_mapped.count == 2

    def test_custom_childarg(self):
        hook = HookMultiplexer(childarg="subject_home_town_here")

        counter = Counter()
        @hook
        def child(event):
            counter.tick()

        hook.fire(subject_home_town_here="child")
        assert counter.incremented(1)

    def test_required_childname(self):
        hook = HookMultiplexer()

        with pytest.raises(TypeError):
            hook.fire()
        
    def test_optional_childname(self):
        hook = HookMultiplexer(raise_on_noname=False)

        with pytest.raises(NameResolutionError):
            hook.fire()

    def test_pass_on_missing(self):
        hook = HookMultiplexer(raise_on_missing=False)

        hook.fire(name="missing")

    def test_missing_hook(self):
        hook = HookMultiplexer(missing=Hook())

        missings = []
        @hook.missing
        def on_missing(event):
            missings.append((event.name, event.name))

        hook.fire(name="nonexistant")
        assert missings == [("nonexistant", "nonexistant")]

    def test_cancelled_preparer(self):
        hook = HookMultiplexer(preparer=CancellableHook())

        @hook
        def derp(event):
            should_never_run()

        @hook.preparer
        def preparer(event):
            event.cancel()

        result = hook.fire(name="derp")
        assert result.cancelled

    def test_cancellable_preparer(self):
        hook = HookMultiplexer(preparer=CancellableHook())

        @hook
        def derp(event):
            assert getattr(event, "cancel", None) == None
            assert event.cancelled == False

        hook.fire(name="derp")

    def test_command_event_return(self):
        hook = HookMultiplexer()

        @hook
        def command(event):
            event.result = "result"

        event = hook.fire(name="command")
        assert event.result == "result"

    def test_missing_preparer_event_return(self):
        hook = HookMultiplexer(raise_on_missing=False, preparer=Hook())

        @hook.preparer
        def preparer(event):
            event.result = "result"

        event = hook.fire(name="missing")
        assert event.result == "result"

    def test_missing_hook_event_return(self):
        hook = HookMultiplexer(missing=Hook())

        @hook.missing
        def missing(event):
            event.result = "result"

        event = hook.fire(name="nonexistant")
        assert event.result == "result"

class TestHookMultiplexerRegistration(object):
    def test_explicit_name(self):
        hook = HookMultiplexer()
        counter = Counter()

        @hook("herp")
        def derp(event):
            counter.tick()

        hook.fire(name="herp")
        assert counter.count == 1
        with pytest.raises(NameResolutionError):
            hook.fire(name="derp")
            
    def test_command_nameinfer(self):
        hook = HookMultiplexer()
        counter = Counter()

        @hook
        def derp(event):
            counter.tick()

        hook.fire(name="derp")
        assert counter.count == 1

    def test_unregister_deletion(self):
        hook = HookMultiplexer()

        @hook
        def handler(event):
            event.handled = True

        event = hook.fire(name="handler")
        assert event.handled

        hook.unregister(handler)

        with pytest.raises(NameResolutionError):
            hook.fire(name="handler")

    def test_multi_unregister(self):
        hook = HookMultiplexer()

        @hook
        def handler1(event):
            should_never_run()

        @hook
        def handler2(event):
            event.handler2 = True

        hook.unregister(handler1)
        event = hook.fire(name="handler2")
        assert event.handler2

        with pytest.raises(NameResolutionError):
            hook.fire(name="handler1")

    def test_not_registered_unregister(self):
        hook = HookMultiplexer()

        @hook
        def handler1(event):
            event.handler1 = True

        def handler2(event):
            should_never_run()

        assert hook.fire(name="handler1").handler1
        
        with pytest.raises(NotRegisteredError):
            hook.unregister(handler2)

    def test_register_once(self):
        hook = HookMultiplexer()
        counter = Counter()

        def handler(event):
            counter.tick()

        hook.register_once(handler)

        hook.fire(name="handler")
        assert counter.incremented(1)

        with pytest.raises(NameResolutionError):
            hook.fire(name="handler")

    def test_register_once_explicitname(self):
        hook = HookMultiplexer()
        counter = Counter()

        def handler(event):
            counter.tick()

        hook.register_once(handler, "handler_name")

        hook.fire(name="handler_name")
        assert counter.incremented(1)

        with pytest.raises(NameResolutionError):
            hook.fire(name="handler_name")

    def test_multi_unregister_samehook(self):
        hook = HookMultiplexer()
        counter = Counter()

        @hook("derp")
        def handler1(event):
            counter.tick()

        @hook("derp")
        def handler2(event):
            counter.tick()

        hook.fire(name="derp")
        assert counter.incremented(2)

        hook.unregister(handler1)
        hook.fire(name="derp")
        assert counter.incremented(1)

        hook.unregister(handler2)
        with pytest.raises(NameResolutionError):
            hook.fire(name="derp")
        
def test_hookmultiplexer_repr():
    hook = HookMultiplexer(name="special_testing_name")

    assert "special_testing_name" in repr(hook)

def test_childhook_repr():
    hook = HookMultiplexer(name="special_testing_name")

    @hook
    def handler(event):
        assert "special_testing_name" in repr(event.calling_hook)
        assert "handler" in repr(event.calling_hook)
        event.ran = True

    event = hook.fire(name="handler")
    assert event.ran

class TestCommandHook(object):
    def test_single_main_handler(self):
        hook = HookMultiplexer(hook_class=CommandHook)
        
        @hook("my_command")
        def my_command(event):
            should_never_run()

        with pytest.raises(AlreadyRegisteredError):
            @hook("my_command")
            def my_conflict(event):
                should_never_run()

    def test_beforeafter_handlers(self):
        hook = HookMultiplexer(hook_class=CommandHook)

        @hook("command", before="main")
        def first(event):
            event.first = True

        @hook
        def command(event):
            assert event.first
            event.command = True

        @hook("command", after="main")
        def after(event):
            assert event.command
            event.after = True

        event = hook.fire(name="command")
        assert event.after

class TestInstanceHook(object):
    def test_simple(self):
        class SomeRandomClass(object):
            hook = InstanceHook()

        @SomeRandomClass.hook
        def preparer(event):
            event.prepared = True

        instance1 = SomeRandomClass()
        instance2 = SomeRandomClass()

        @instance1.hook
        def handler1(event):
            assert event.prepared
            event.handler1 = True

        @instance2.hook
        def handler2(event):
            assert event.prepared
            event.handler2 = True

        event = instance1.hook.fire()
        assert event.handler1

        event = instance2.hook.fire()
        assert event.handler2

    def test_per_instance_mutliplexers(self):
        class HasHook(object):
            hook = InstanceHook(hook_class=lambda: HookMultiplexer(preparer=Hook()))

        instance = HasHook()

        @instance.hook.preparer
        def preparer(event):
            event.prepared = True

        @instance.hook
        def command(event):
            assert event.prepared
            event.command = True

        event = instance.hook.fire(name="command")
        assert event.command

    def test_instance_unregister(self):
        class HasHook(object):
            hook = InstanceHook()

        instance = HasHook()

        @instance.hook
        def handler(event):
            event.handled = True

        event = instance.hook.fire()
        assert event.handled

        instance.hook.unregister(handler)

        event = instance.hook.fire()
        assert "handled" not in event

    def test_class_unregister(self):
        class HasHook(object):
            hook = InstanceHook()

        @HasHook.hook
        def handler(event):
            event.handled = True

        instance = HasHook()
        event = instance.hook.fire()
        assert event.handled

        HasHook.hook.unregister(handler)

        event = instance.hook.fire()
        assert "handled" not in event

    def test_wrong_unregister(self):
        class HasHook(object):
            hook = InstanceHook()

        @HasHook.hook
        def preparer(event):
            event.prepared = True

        instance = HasHook()

        @instance.hook
        def handler(event):
            assert event.prepared
            event.handled = True

        event = instance.hook.fire()
        assert event.handled

        with pytest.raises(NotRegisteredError):
            instance.hook.unregister(preparer)

        with pytest.raises(NotRegisteredError):
            HasHook.hook.unregister(handler)

        event = instance.hook.fire()
        assert event.handled

    def test_register_once(self):
        class HasHook(object):
            hook = InstanceHook()

        instance = HasHook()

        def handler(event):
            event.handled = True

        instance.hook.register_once(handler)
        event = instance.hook.fire()
        assert event.handled
        event = instance.hook.fire()
        assert "handled" not in event

    def test_register_once_class(self):
        class HasHook(object):
            hook = InstanceHook()

        instance = HasHook()

        def handler(event):
            event.handled = True

        HasHook.hook.register_once(handler)

        event = instance.hook.fire()
        assert event.handled
        event = instance.hook.fire()
        assert "handled" not in event
