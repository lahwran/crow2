import pytest

import crow2.test.setup # pylint: disable = W0611
from crow2.test.util import Counter
from crow2.events import exceptions
from crow2.events.hook import Hook
from crow2.events.handlerclass import (HookMethodProxy, instancehandler,
        handlermethod, _get_method_regs, _HandlerClass, handlerclass)
from crow2.util import AttrDict


def proxied_method(self, event=None):
    self.counter.tick()


class TestHookMethodProxy(object):
    def test_methodproxying(self):
        class ProxiedClass(object):
            def __init__(self):
                self.counter = Counter()

            proxied_method = proxied_method

        proxy = HookMethodProxy(proxied_method)

        proxy()

        instance1 = ProxiedClass()
        instance2 = ProxiedClass()
        proxy.add_bound_method(instance1.proxied_method, None)
        proxy()
        assert instance1.counter.incremented(1)
        assert instance2.counter.incremented(0)

        proxy.add_bound_method(instance2.proxied_method, None)
        proxy()
        assert instance1.counter.incremented(1)
        assert instance2.counter.incremented(1)

        proxy.remove_bound_method(instance2.proxied_method)
        proxy()
        assert instance1.counter.incremented(1)
        assert instance2.counter.incremented(0)

        with pytest.raises(exceptions.AlreadyRegisteredError):
            proxy.add_bound_method(instance1.proxied_method, None)

        proxy.remove_bound_method(instance1.proxied_method)
        proxy()
        assert instance1.counter.incremented(0)
        assert instance2.counter.incremented(0)


        with pytest.raises(exceptions.NotRegisteredError):
            proxy.remove_bound_method(instance1.proxied_method)

    def test_class_registration(self):
        class ProxiedClass(object):
            def __init__(self):
                self.counter = Counter()
            proxied_method = proxied_method

        class ProxiedClass2(object):
            def __init__(self):
                self.counter = Counter()
            proxied_method = proxied_method

        proxy = HookMethodProxy(proxied_method)

        hook0 = Hook()
        hook1 = Hook()

        instance1 = ProxiedClass()
        instance2 = ProxiedClass2()

        # simply adding the hook just indicates that
        # when a class is ready to use the proxy,
        # the hook will be registered; it doesn't
        # do anything else
        proxy.addhook(hook0, (), {})
        hook0.fire()
        assert instance1.counter.incremented(0)

        proxy.register(ProxiedClass, "proxied_method")
        proxy.add_bound_method(instance1.proxied_method, None)
        hook0.fire()
        assert instance1.counter.incremented(1)

        with pytest.raises(exceptions.AlreadyRegisteredError):
            proxy.register(ProxiedClass, "proxied_method")

        proxy.addhook(hook1, (), {})
        hook1.fire()
        assert instance1.counter.incremented(1)

        proxy.register(ProxiedClass2, "proxied_method")
        proxy.add_bound_method(instance2.proxied_method, None)
        hook1.fire()
        assert instance2.counter.incremented(1)
        assert instance1.counter.incremented(1)

        proxy.remove_bound_method(instance1.proxied_method)
        proxy.unregister(ProxiedClass, "proxied_method")
        hook1.fire()
        assert instance2.counter.incremented(1)
        assert instance1.counter.incremented(0)

        proxy.remove_bound_method(instance2.proxied_method)
        proxy.unregister(ProxiedClass2, "proxied_method")

        with pytest.raises(exceptions.NotRegisteredError):
            proxy.unregister(ProxiedClass2, "proxied_method")

        hook1.fire()
        assert instance2.counter.incremented(0)
        assert instance1.counter.incremented(0)

def test_instancehandler():
    class Target(object):
        def __init__(self):
            self.counter = Counter()

        @instancehandler.thing.hook
        @instancehandler.otherthing.otherhook()
        @instancehandler.argthing.arg(derp=True)
        def a_method(self, event):
            self.counter.tick()

    a_method = vars(Target)["a_method"]
    regs = a_method._crow2_instancehookregs
    by_names = dict([(reg.names, reg) for reg in regs])

    assert set(by_names.keys()) == set((("thing", "hook"), ("otherthing", "otherhook"), ("argthing", "arg")))

    instances = [Target(), Target()]

    unregister_counter = Counter()

    for instance in instances:
        simple_counter = Counter()
        partial_counter = Counter()
        arg_counter = Counter()

        def simpledecorator(func):
            simple_counter.tick()

        def partialdecorator():
            partial_counter.tick()
            def partial(func):
                partial_counter.tick()
            return partial

        def argdecorator(derp):
            arg_counter.tick()
            def partial(func):
                arg_counter.tick()
            return partial
        argdecorator.unregister = lambda func: unregister_counter.tick()
        partialdecorator.unregister = lambda func: unregister_counter.tick()
        simpledecorator.unregister = lambda func: unregister_counter.tick()

        event = AttrDict()
        event.thing = AttrDict(hook=simpledecorator)
        event.otherthing = AttrDict(otherhook=partialdecorator)
        event.argthing = AttrDict(arg=argdecorator)

        by_names["thing", "hook"].add_bound_method(instance.a_method, event)
        assert simple_counter.incremented(1)

        by_names["otherthing", "otherhook"].add_bound_method(instance.a_method, event)
        assert partial_counter.incremented(2)

        by_names["argthing", "arg"].add_bound_method(instance.a_method, event)
        assert arg_counter.incremented(2)

    for instance in instances:
        by_names["thing", "hook"].remove_bound_method(instance.a_method)
        by_names["otherthing", "otherhook"].remove_bound_method(instance.a_method)
        by_names["argthing", "arg"].remove_bound_method(instance.a_method)
        assert unregister_counter.incremented(3)

def test_handlermethod():
    hook0 = object()
    hook1 = object()

    @handlermethod(hook0)
    @handlermethod(hook1)
    def handler():
        pass

    hooks = handler._crow2_hookmethodproxy.registrations
    assert len(hooks) == 2
    assert (hook0, (), {}) in hooks
    assert (hook1, (), {}) in hooks

def test_get_method_regs():
    hook0 = object()
    hook1 = object()

    @handlermethod(hook0)
    @handlermethod(hook1)
    @instancehandler.thing.hook
    @instancehandler.otherthing.derp()
    @instancehandler.derp(asdf="derp")
    @instancehandler
    def handler():
        pass

    assert len(_get_method_regs(handler)) == 5
    regs = _get_method_regs(handler)[0].registrations
    assert len(regs) == 2
    assert (hook0, (), {}) in regs
    assert (hook1, (), {}) in regs
    assert set(x.names for x in _get_method_regs(handler)[1:]) == set((("thing", "hook"), ("otherthing", "derp"), ("derp",), ()))

    def handler():
        pass

    assert len(_get_method_regs(handler)) == 0

def test_class_reg():
    registrations = []
    def register(handler, *args, **keywords):
        registrations.append((handler, args, keywords))

    hook = AttrDict(register=register)
    @handlerclass(hook)
    @handlerclass(hook, "derp")
    @handlerclass(hook, derp=True)
    class Target(object):
        pass

    assert registrations == [(Target._crow2_classreg, (), {"derp": True}),
                             (Target._crow2_classreg, ("derp",), {}),
                             (Target._crow2_classreg, (), {})]

class DummyAttributeRegistration(object):
    def __init__(self):
        self.registereds = []
        self.unregistereds = []
        self.bounds = []
        self.unbounds = []

    def register(self, clazz, name):
        self.registereds.append((clazz, name))
    def unregister(self, clazz, name):
        self.unregistereds.append((clazz, name))
    def add_bound_method(self, bound_method, event):
        self.bounds.append((bound_method, event))
    def remove_bound_method(self, bound_method):
        self.unbounds.append(bound_method)

class TestHandlerClass(object):
    def test_simple(self):
        class Clazz(object):
            def __init__(self, event):
                pass
            def herp(self):
                pass
            herp._crow2_instancehookregs = [DummyAttributeRegistration()]
            def derp(self):
                self.delete()
        herp = vars(Clazz)["herp"]
        dummy = herp._crow2_instancehookregs[0]

        reg = _HandlerClass(Clazz)
        assert len(dummy.registereds) == 0
        assert len(dummy.bounds) == 0

        event = AttrDict()
        instance = reg(event)
        assert dummy.registereds == [(Clazz, "herp")]
        assert dummy.bounds == [(instance.herp, event)]

        instance.derp()
        assert dummy.unbounds == [instance.herp]
        assert dummy.unregistereds == [(Clazz, "herp")]

    def test_errors(self, capsys):
        class Clazz(object):
            def __init__(self, event):
                pass
            def delete(self):
                pass

        reg = _HandlerClass(Clazz)

        event = AttrDict()
        instance2 = Clazz(event)

        with pytest.raises(exceptions.NotRegisteredError):
            reg.free_instance(instance2)

        out, err = capsys.readouterr()

        reg(event)

        out, err = capsys.readouterr()
        assert "WARNING" in out or "WARNING" in err

        class OtherClazz(object):
            def __init__(self, event):
                pass
            __init__._crow2_instancehookregs = [DummyAttributeRegistration()]
        with pytest.raises(exceptions.NotInstantiableError):
            otherreg = _HandlerClass(OtherClazz)

def test_integration():
    hook1 = Hook()
    hook2 = Hook()
    hook_method = Hook()

    @handlerclass(hook1)
    @handlerclass(hook2)
    class Clazz(object):
        def __init__(self, event):
            event.counter.tick()

        @handlermethod(hook_method)
        def a_method(self, event):
            event.other_counter.tick()

        @instancehandler.hook(tag="derp")
        def a_handler(self, event):
            event.counter2.tick()

        @instancehandler.hook_destroy
        def destroy(self, event):
            self.delete()

    result = hook_method.fire(other_counter=Counter())
    assert result.other_counter.incremented(0)

    hook1_result = hook1.fire(hook=Hook(), hook_destroy=Hook(), counter=Counter())
    hook2_result = hook2.fire(hook=Hook(), hook_destroy=Hook(), counter=Counter())
    assert hook1_result.counter.incremented(1)
    assert hook2_result.counter.incremented(1)

    result = hook_method.fire(other_counter=Counter())
    assert result.other_counter.incremented(2)

    print hook2_result.hook
    hook3_result = hook2_result.hook.fire(counter2=Counter())
    assert hook3_result.counter2.incremented(1)

    hook1_result.hook_destroy.fire()
    result = hook_method.fire(other_counter=Counter())
    assert result.other_counter.incremented(1)

    hook2_result.hook_destroy.fire()
    result = hook_method.fire(other_counter=Counter())
    assert result.other_counter.incremented(0)
    hook3_result = hook2_result.hook.fire(counter2=Counter())
    assert hook3_result.counter2.incremented(0)
