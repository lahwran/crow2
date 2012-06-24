import pytest
from zope.interface import Interface, implementer
from zope.interface.adapter import AdapterRegistry

from crow2 import adapterutil

def test_simple(monkeypatch):
    monkeypatch.setattr(adapterutil, "registry", AdapterRegistry())

    class IFrom(Interface):
        pass

    @implementer(IFrom)
    class From(object):
        pass

    class ITo(Interface):
        pass

    class To(object):
        def __init__(self, from_obj):
            self.from_obj = from_obj

    adapterutil.register(To, From, ITo)

    from_obj = From()
    result = ITo(from_obj)
    assert isinstance(result, To)
    assert result.from_obj is from_obj

def test_infer_implements(monkeypatch):
    monkeypatch.setattr(adapterutil, "registry", AdapterRegistry())

    class IFrom(Interface):
        pass
    @implementer(IFrom)
    class From(object):
        pass
    class ITo(Interface):
        pass
    @implementer(ITo)
    class To(object):
        def __init__(self, from_obj):
            self.from_obj = from_obj

    adapterutil.register(To, From)

    from_obj = From()
    result = ITo(from_obj)
    assert isinstance(result, To)
    assert result.from_obj is from_obj

def test_fakeimplementor(monkeypatch):
    monkeypatch.setattr(adapterutil, "registry", AdapterRegistry())

    class ITo(Interface):
        pass

    @implementer(ITo)
    def convert(obj):
        return str(obj)

    adapterutil.register(convert, int)

    assert ITo(5) == "5"

def test_deregister(monkeypatch):
    monkeypatch.setattr(adapterutil, "registry", AdapterRegistry())

    class IFrom(Interface):
        pass
    @implementer(IFrom)
    class From(object):
        pass
    class ITo(Interface):
        pass
    class To(object):
        def __init__(self, from_obj):
            self.from_obj = from_obj

    adapterutil.register(To, From, ITo)

    from_obj = From()
    assert isinstance(ITo(from_obj), To)

    adapterutil.deregister(To, From, ITo)

    with pytest.raises(TypeError):
        ITo(from_obj)

def test_deregister_infer(monkeypatch):
    monkeypatch.setattr(adapterutil, "registry", AdapterRegistry())

    class IFrom(Interface):
        pass
    @implementer(IFrom)
    class From(object):
        pass
    class ITo(Interface):
        pass
    @implementer(ITo)
    class To(object):
        def __init__(self, from_obj):
            self.from_obj = from_obj

    adapterutil.register(To, From)

    from_obj = From()
    assert isinstance(ITo(from_obj), To)

    adapterutil.deregister(To, From)

    with pytest.raises(TypeError):
        ITo(from_obj)
