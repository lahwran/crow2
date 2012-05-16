"""
Tests for the util module
"""
# pylint: disable = W0612
import crow2.util
import pytest

class TestParamdecorator(object):
    """
    Test @paramdecorator in various ways
    """
    def test_simple(self):
        """
        A simple test to make sure that paramdecorator works on a no-argument decorator
        """
        runs = []
        @crow2.util.paramdecorator
        def simple(func):
            "Simple decorator"
            runs.append(func)
            return func

        @simple
        def afunc():
            "stub to decorate"
            pass
        assert runs[-1] is afunc
        @simple()
        def afunc2():
            "stub to decorate"
            pass
        assert runs[-1] is afunc2
        with pytest.raises(TypeError):
            @simple("somearg")
            def afunc3():
                "stub to decorate"
                pass

    def test_requiredarg(self):
        """
        Test that paramdecorator produces a decorator with one required arg out of
        a function with a func arg and a required arg
        """
        lastrun = []
        @crow2.util.paramdecorator
        def decorator(func, requiredarg):
            "Decorator with one required arg"
            del lastrun[:]
            lastrun.extend((func, requiredarg))
            return func

        with pytest.raises(TypeError):
            @decorator
            def afunc():
                "stub to decorate"
                pass

        somearg = object()
        @decorator(somearg)
        def afunc2():
            "stub to decorate"
            pass
        assert lastrun[0] is afunc2
        assert lastrun[1] is somearg

        somearg = object()
        @decorator(requiredarg=somearg)
        def afunc3():
            "stub to decorate"
            pass
        assert lastrun[0] is afunc3
        assert lastrun[1] is somearg


    def test_optionalarg(self):
        """
        Test that an optional argument behaves as expected.
        Additionally, test that self detection and method binding works as expected.
        """
        lastrun = []
        class Derp(object):
            """
            class to test self with
            """
            def __init__(self, lastrun):
                self.lastrun = lastrun

            @crow2.util.paramdecorator
            def decorator(self, func, optionalarg1=None, optionalarg2=None):
                "Decorator method with two optional args"
                del self.lastrun[:]
                self.lastrun.extend((func, optionalarg1, optionalarg2))
                return func

        decorator = Derp(lastrun).decorator

        @decorator
        def afunc1():
            "stub to decorate"
            pass
        assert lastrun[0] is afunc1
        assert lastrun[1] is None
        assert lastrun[2] is None

        @decorator()
        def afunc2():
            "stub to decorate"
            pass
        assert lastrun[0] is afunc2
        assert lastrun[1] is None
        assert lastrun[2] is None

        somearg = object() # object with unique identity for 'is' test
        @decorator(optionalarg1=somearg)
        def afunc3():
            "stub to decorate"
            pass
        assert lastrun[0] is afunc3
        assert lastrun[1] is somearg
        assert lastrun[2] is None

        somearg = object()
        with pytest.raises(TypeError):
            @decorator(derp=somearg) # pylint: disable = E1123
            def afunc4():
                "stub to decorate"
                pass

    def test_quirks(self):
        """
        Test that known paramdecorator quirks misbehave as expected
        """
        lastrun = []
        @crow2.util.paramdecorator
        def decorator(func, func2):
            "decorator which records calls to it and calls both arguments"
            del lastrun[:]
            lastrun.extend((func, func2))
            return func() + func2()

        def func2():
            "function to pass into decorator"
            return "func2"

        with pytest.raises(TypeError):
            @decorator(func2) # this is like doing @decorator\ndef func2(): and as such does not pass
            def dead_func():       # enough arguments to the decorator
                "function which never gets touched by decorator"
                return "func" #pragma: no cover

        @decorator(func2=func2)
        def successful_func():
            "function which gets succesfully called by decorator"
            return "func"
        assert successful_func == "funcfunc2"
        assert lastrun[1] is func2

    def test_argnum(self):
        thing1_sentinel = object()
        thing2_sentinel = object()
        @crow2.util.paramdecorator(argnum=2)
        def with_args(thing1, thing2, func):
            assert thing1 is thing1_sentinel
            assert thing2 is thing2_sentinel
            assert func

        @with_args(thing1_sentinel, thing2_sentinel)
        def afunc_1():
            pass

        @crow2.util.paramdecorator(argnum=1, argname="function")
        def with_undetectable_args(*args):
            thing1, func, thing2 = args
            assert thing1 is thing1_sentinel
            assert thing2 is thing2_sentinel
            assert func

        @with_undetectable_args(thing1_sentinel, thing2_sentinel)
        def afunc_2():
            pass

        def newfunc():
            pass
        with_undetectable_args(thing1_sentinel, thing2_sentinel, function=newfunc)

        @crow2.util.paramdecorator(argname="target")
        def with_named_target(thing1, thing2, target):
            assert thing1 is thing1_sentinel
            assert thing2 is thing2_sentinel
            assert target

        @with_named_target(thing1_sentinel, thing2_sentinel)
        def afunc_3():
            pass

        
        @crow2.util.paramdecorator(argname="target")
        def only_named_target(target):
            assert target

        @only_named_target
        def afunc_4():
            pass

        class Derp(object):
            @crow2.util.paramdecorator(useself=True)
            def method_decorator(nonstandard_self, target):
                assert nonstandard_self.__class__ is Derp
                assert target

        herp = Derp()
        @herp.method_decorator
        def afunc_5():
            pass

        with pytest.raises(Exception):
            @crow2.util.paramdecorator(useself=False, argnum=0)
            def conflicting_target_id():
                pass
        with pytest.raises(Exception):
            @crow2.util.paramdecorator(argname="nonexistant")
            def nonexistant_target(target):
                pass

def test_attrdict():
    attrdict = crow2.util.AttrDict()
    attrdict.blah = 1
    assert attrdict.blah
    assert attrdict == {"blah": 1}
    with pytest.raises(AttributeError):
        assert attrdict.doesnotexis

