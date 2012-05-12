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
    def test_paramdecorator_simple(self):
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

    def test_paramdecorator_requiredarg(self):
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


    def test_paramdecorator_optionalarg(self):
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

    def test_paramdecorator_quirks(self):
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
