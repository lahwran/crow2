import pytest

from crow2.events.util import LazyCall
from crow2.util import AttrDict
from crow2.test.util import Counter, should_never_run
from crow2.events import exceptions

def test_lazy_call():
    lazycall = LazyCall(("herp", "derp"), ("args",), {"key": "words"}, False)
    counter = Counter()

    def target(value, key):
        assert value == "args"
        assert key == "words"
        counter.tick()

    herp = AttrDict(derp=target)
    obj = AttrDict(herp=herp)

    assert counter.incremented(0)
    lazycall.resolve(obj)
    assert counter.incremented(1)

def test_lazy_missing():
    lazycall = LazyCall(("doesnt", "exist", "attribute"), ("argument",), {"key": "value"}, False)

    exist = AttrDict()
    doesnt = AttrDict(exist=exist)
    obj = AttrDict(doesnt=doesnt)
    try:
        lazycall.resolve(obj)
    except AttributeError as e:
        assert "doesnt.exist" in e.message
        assert "attribute" in e.message
        assert "key" in e.message
        assert "value" in e.message
        assert "argument" in e.message
        assert repr(obj) in e.message
    else:
        should_never_run()

def test_lazy_decorate():
    lazycall = LazyCall(("decorator",), (), {}, True, True)
    decorate_count = Counter()

    def sentinel_func():
        should_never_run()

    def simple_decorator(func):
        assert func is sentinel_func
        decorate_count.tick()

    obj = AttrDict(decorator=simple_decorator)
    lazycall.resolve(obj, sentinel_func)

    assert decorate_count.incremented(1)

def test_lazy_decorate_missing():
    lazycall = LazyCall((), (), {}, True, True)

    with pytest.raises(exceptions.DecoratedFuncMissingError):
        lazycall.resolve(AttrDict(), None)

def test_complex_decorator():
    lazycall = LazyCall((), ("arg1", "arg2"), {"key": "word"}, True, False)
    complex_counter = Counter()
    actual_counter = Counter()

    def sentinel_func():
        should_never_run()

    def complex_decorator(arg1, arg2, key=False):
        assert arg1 == "arg1"
        assert arg2 == "arg2"
        assert key == "word"
        def actual_decorator(func):
            assert func is sentinel_func
            actual_counter.tick()
        complex_counter.tick()
        return actual_decorator

    lazycall.resolve(complex_decorator, sentinel_func)

    assert complex_counter.incremented(1)
    assert actual_counter.incremented(1)

def test_exception_in_call():
    lazycall = LazyCall(("herp", "derp"), ("positional_arg",), {"keyword": "kwarg"}, False)

    class SentinelException(Exception):
        pass

    def target(positional_arg, keyword):
        assert positional_arg == "positional_arg"
        assert keyword == "kwarg"
        raise SentinelException()

    herp = AttrDict(derp=target)
    obj = AttrDict(herp=herp)
    try:
        lazycall.resolve(obj)
    except exceptions.ExceptionInCallError as e:
        assert "SentinelException" in e.message
        assert "target" in e.message
        assert "herp.derp" in e.message
    else:
        should_never_run()

def test_not_really_complex():
    sentinel = object()
    lazycall = LazyCall((), (sentinel,), {}, True, False)

    def sentinel_func():
        should_never_run()

    def target(func):
        assert func is sentinel

    try:
        lazycall.resolve(target, sentinel_func)
    except exceptions.ExceptionInCallError as e:
        assert "sentinel_func" in e.message
        assert "target" in e.message
        assert "NoneType" in e.message
    else:
        should_never_run()

def test_repr():
    lazycall = LazyCall(("herp", "derp"), ("positional_arg",), {"keyword": "kwarg"}, False)

    repred = repr(lazycall)
    assert "herp.derp" in repred
    assert "positional_arg" in repred
    assert "keyword" in repred
    assert "kwarg" in repred

def test_decorator_repr():
    lazycall = LazyCall(("herp", "derp"), ("positional_arg",), {"keyword": "kwarg"}, True, False)

    repred = repr(lazycall)
    assert "herp.derp" in repred
    assert "positional_arg" in repred
    assert "keyword" in repred
    assert "kwarg" in repred
    assert "func" in repred

def test_simple_decorator_repr():
    lazycall = LazyCall(("herp", "derp"), ("positional_arg",), {"keyword": "kwarg"}, True)

    repred = repr(lazycall)
    assert "herp.derp" in repred
    assert "positional_arg" not in repred
    assert "kwarg" not in repred
    assert "keyword" not in repred
