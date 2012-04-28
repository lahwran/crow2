from crow2 import events
from crow2 import toposort
import pytest
import crow2.test.setup

class Counter(object):
    "a mutable counter"
    def __init__(self):
        self.count = 0
    def tick(self):
        self.count += 1

class TestYielding(object):
    def test_simple(self):
        hook1 = events.Hook()
        hook2 = events.Hook()

        @hook1
        @events.yielding
        def handler(event):
            while "derp" in event:
                event, = yield event.derp
            event.was_called = True

        assert "was_called" in hook1.fire()

        assert not "was_called" in hook2.fire()

#        import pdb; pdb.set_trace()
        assert not "was_called" in hook1.fire(derp=hook2)
        assert "was_called" in hook2.fire()

        assert not "was_called" in hook2.fire()

        assert not "was_called" in hook1.fire(derp=hook2)
        assert not "was_called" in hook2.fire(derp=hook1)
        assert not "was_called" in hook1.fire(derp=hook2)
        assert "was_called" in hook2.fire()

def test_class_reg_errors():
    hook = events.Hook()
    hook2 = events.Hook()
    class Clazz(object):
        @hook2.method
        def __init__(self, event):
            pass

    with pytest.raises(events.NotInstantiableError):
        registration = events.ClassRegistration(hook, Clazz)

    class Clazz(object):
        def __init__(self):
            pass

        @hook2.method
        def amethod(self, event):
            pass

    registration = events.ClassRegistration(hook, Clazz)
    registration.register_proxies()

    with pytest.raises(events.AlreadyRegisteredError):
        registration()

    class Clazz(object):
        def __init__(self):
            self.parent_registration = None
        def delete(self):
            pass

    registration = events.ClassRegistration(hook, Clazz)
    instance = registration()
    instance.delete()

    instance = Clazz()
    with pytest.raises(events.NotRegisteredError):
        registration.free_instance(instance)

    instance = registration()
    registration.unregister_proxies()
    with pytest.raises(events.NotRegisteredError):
        instance.delete()

def test_method_proxy_errors():
    hook = events.Hook()
    class Clazz(object):
        @hook.method
        def amethod(self):
            pass
    methodfunc = Clazz.__dict__['amethod']
    proxy = events.MethodProxy(Clazz, methodfunc.__name__, methodfunc,
                    events.MethodProxy._get_method_regs(methodfunc))
    proxy.register()
    with pytest.raises(events.AlreadyRegisteredError):
        proxy.register()
    proxy.unregister()
    with pytest.raises(events.NotRegisteredError):
        proxy.unregister()

    instance = Clazz()
    proxy.add_bound_method(instance)
    with pytest.raises(events.AlreadyRegisteredError):
        proxy.add_bound_method(instance)

    proxy.remove_bound_method(instance)
    with pytest.raises(events.NotRegisteredError):
        proxy.remove_bound_method(instance)

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
            hook.unregister(callonce)

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

    def test_get_name(self):
        hook = events.Hook()
        assert hook._get_name(TestHook) == "crow2.test.test_events.TestHook"

        from crow2.test import hook_reference_target
        assert hook._get_name(hook_reference_target) == "crow2.test.hook_reference_target"

        assert hook._get_name(self.test_dependency_lookup) == "crow2.test.test_events.TestHook.test_dependency_lookup"

        assert hook._get_name(test_attrdict) == "crow2.test.test_events.test_attrdict"

        with pytest.raises(Exception):
            hook._get_name(5)

        class Immutable(object):
            "test to ensure caching does not cause any unexpected behavior"
            __slots__ = ()

        immutable_instance = Immutable()

        # NOTE: this is not the behavior people probably expect! will need documenting
        assert hook._get_name(Immutable) == "crow2.test.test_events.Immutable"
        assert hook._get_name(Immutable) == "crow2.test.test_events.Immutable"

    def test_class_hook(self):
        hook_init = events.Hook()
        hook_run = events.Hook()
        hook_cleanup = events.Hook()
        the_value = "method was run"
        the_second_value = "method was not run"

        @hook_init.instantiate
        class ClassHandler(object):
            def __init__(self, event):
                self.value = event.value

            @hook_run.method
            def amethod(self, event):
                event.value = self.value

            @hook_cleanup.method
            def free(self, event):
                self.delete()

        hook_init.fire(value=the_value)
        assert hook_run.fire(value=the_second_value).value == the_value
        hook_cleanup.fire()
        assert hook_run.fire(value=the_second_value).value == the_second_value

    def test_class_referencing(self):
        hook_init = events.Hook()
        hook_run = events.Hook()
        hook_cleanup = events.Hook()
        counter = Counter()

        @hook_init.instantiate
        class ClassHandler(object):
            def __init__(self, event):
                pass

            @hook_run.method
            def target1(self, event):
                print "target1"
                assert event.target1_before
                event.target1 = True
                counter.tick()

            @hook_cleanup.method
            def cleanup(self, event):
                self.delete()

        @hook_run(before="ClassHandler.target1")
        def target1_before(event):
            print "target1_before"
            event.target1_before = True

        @hook_run(after=ClassHandler.target1)
        def target1_after(event):
            print "target1_after"
            assert event.target1
            event.target1_after = True

        hook_init.fire()
        hook_init.fire()
        run = hook_run.fire()
        assert run.target1_after
        assert counter.count == 2
        hook_cleanup.fire()

    def test_unresolvable_object(self, capsys):
        hook = events.Hook()
        hook.register(tuple())

        out, err = capsys.readouterr()

        assert "WARNING" in out

        hook.unregister(tuple())

        out, err = capsys.readouterr()

        assert "WARNING" in out



def test_attrdict():
    d = events.AttrDict()
    d.blah = 1
    assert d.blah
    assert d == {"blah": 1}
    with pytest.raises(AttributeError):
        d.doesnotexis

'''
def test_idea():
    class Arguments(tuple):
        def _add_dict(self, d):
            self.keywords = d
        def __getattr__(self, attr):
            try:
                return self.keywords[attr]
            except KeyError:
                raise AttributeError
    derp = Arguments((1, 2))
    derp._add_dict(dict(c=5, d=6))
    a, b = derp
    assert a == 1
    assert b == 2
    assert tuple(derp) == (1, 2)
    assert derp.c == 5
    assert derp.d == 6

def test_other_idea():
    class Arguments(tuple):
        def _add_dict(self, d):
            self.keywords = d
        def __getitem__(self, item):
            try:
                return super(Arguments, self).__getitem__(item)
            except TypeError:
                return self.keywords[item]
    derp = Arguments((1, 2))
    derp._add_dict(dict(c=5, d=6))
    a, b = derp
    assert a == 1
    assert b == 2
    assert tuple(derp) == (1, 2)
    assert derp["c"] == 5
    assert derp["d"] == 6
    assert derp[0] == 1
    assert derp[1] == 2

def test_somewhat_better_idea():


    derp = Arguments((1, 2), dict(c=5, d=6))
    a, b = derp
    assert a == 1
    assert b == 2
    assert tuple(derp) == (1, 2)
    assert derp.c == 5
    assert derp.d == 6
    assert derp["c"] == 5
    assert derp["d"] == 6
    assert derp[0] == 1
    assert derp[1] == 2
    with pytest.raises(KeyError):
        derp["e"]
    with pytest.raises(IndexError):
        derp[4]
    with pytest.raises(AttributeError):
        derp.f'''