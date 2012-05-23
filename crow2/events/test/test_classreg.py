from crow2.events import exceptions
from crow2.events._base import DecoratorHook
from crow2.events._classreg import ClassRegistration, MethodProxy, ClassregHookMixin
from crow2.test.testutil import Counter
import crow2.test.setup # pylint: disable = W0611
import pytest

class MixedHook(DecoratorHook, ClassregHookMixin):
    pass

def test_class_reg_errors():
    """
    Test that ClassRegistration things which raise an error raise them at the right times
    """
    hook_sentinel = object()
    hook2 = MixedHook()
    class Clazz(object):
        "A class which will cause an error on attempted instantiation"
        @hook2.method
        def __init__(self, event):
            "An init with an unacceptable registration"
            pass

    with pytest.raises(exceptions.NotInstantiableError):
        registration = ClassRegistration(hook_sentinel, Clazz)

    class Clazz(object):
        "A proxied class which should not cause any errors to register"
        def __init__(self):
            pass

        @hook2.method
        def amethod(self, event):
            "A method with a registration"
            pass

    registration = ClassRegistration(hook_sentinel, Clazz)
    registration.register_proxies()

    with pytest.raises(exceptions.AlreadyRegisteredError):
        registration()

    class Clazz(object):
        "A class which will cause a warning on registration"
        def __init__(self):
            self.parent_registration = None
        def delete(self):
            "A delete method which will cause a warning when the ClassRegistration overwrites it"
            pass

    registration = ClassRegistration(hook_sentinel, Clazz)
    instance = registration()
    instance.delete()

    instance = Clazz()
    with pytest.raises(exceptions.NotRegisteredError):
        registration.free_instance(instance)

    instance = registration()
    registration.unregister_proxies()
    with pytest.raises(exceptions.NotRegisteredError):
        instance.delete()

def test_method_proxy_errors():
    """
    Test that known invalid method proxy states cause errors
    """
    hook = MixedHook()
    class Clazz(object):
        "A Class which has a method"
        @hook.method
        def amethod(self):
            "a method to be pulled out and put into a method proxy"
            pass
    methodfunc = Clazz.__dict__['amethod']
    proxy = MethodProxy(Clazz, methodfunc.__name__, methodfunc,
                    MethodProxy._get_method_regs(methodfunc))
    proxy.register()
    with pytest.raises(exceptions.AlreadyRegisteredError):
        proxy.register()
    proxy.unregister()
    with pytest.raises(exceptions.NotRegisteredError):
        proxy.unregister()

    instance = Clazz()
    proxy.add_bound_method(instance)
    with pytest.raises(exceptions.AlreadyRegisteredError):
        proxy.add_bound_method(instance)

    proxy.remove_bound_method(instance)
    with pytest.raises(exceptions.NotRegisteredError):
        proxy.remove_bound_method(instance)

def test_class_hook():
    hook_init = MixedHook()
    hook_run = MixedHook()
    hook_cleanup = MixedHook()
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

def test_class_referencing():
    hook_init = MixedHook()
    hook_run = MixedHook()
    hook_cleanup = MixedHook()
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

