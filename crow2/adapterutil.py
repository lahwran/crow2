"""
Utilities to allow actual use of zope.interface's adapters. Dunno why these don't ship by default
"""

from zope.interface.adapter import AdapterRegistry
from zope.interface.interface import adapter_hooks, InterfaceClass
from zope.interface import Interface, implementedBy, providedBy
from zope.interface.common.sequence import IWriteSequence, IExtendedReadSequence

registry = AdapterRegistry()

class INumber(Interface):
    "A number, whole, real, or otherwise"

class IInteger(INumber):
    "An integer"

class IReal(INumber):
    "A real number"

class IString(IExtendedReadSequence):
    "A string-like sequence of characters"

class IObjectSequence(IExtendedReadSequence):
    "A sequence of objects - potentially characters - which are independent"

class ITuple(IObjectSequence):
    "A tuple or very similar object"

class IList(IObjectSequence, IWriteSequence):
    "A list or very similar object"


fakeimplementeds = {
    int: IInteger,
    float: IReal,
    str: IString,
    list: IList,
    tuple: ITuple
#    set: ISet
}


def register(implementor, orig, *target_interfaces):
    """
    Register an implementor to map from one interface to another

    .. python::
        from zope.interface import implementer
        # implement*e*r is a typo in zope.interface, unfortunately

        @implementer(ITarget)
        class Implementor(stuff):
            stuff

        register(Implementor, IOriginal)

    .. python::
        from zope.interface import implementer

        @implementer(ITarget1)
        @implementer(ITarget2)
        @implementer(INotTarget)
        class Implementor(stuff):
            stuff

        register(Implementor, IOriginal, ITarget1, ITarget2, ITargetNotImplemented)

    :Parameters:
      implementor
        Factory which returns an object which provides the target interface; if no interfaces
        are passed in, then the target interfaces will be inferred from the list of interfaces
        that the implementor implements.

        Note that this means that if you pass in any target interfaces, they will override the
        inferred ones
      orig
        Interface or class to map from. If it's a class, it must implement exactly one interface.
      target_interfaces
        zero or more target interfaces to map to
    """
    if orig in fakeimplementeds:
        orig_interface = fakeimplementeds[orig]
    elif not isinstance(orig, InterfaceClass):
        orig_interface = implementedBy(orig)
    else:
        orig_interface = orig

    if not target_interfaces:
        target_interfaces = tuple(implementedBy(implementor))

    for target_interface in target_interfaces:
        registry.register([orig_interface], target_interface, '', implementor)

def adapter_for(orig, *target_interfaces):
    """
    Decorator-factory version of register()

    .. python::
        from zope.interface import implementer
        # implement*e*r is a typo in zope.interface, unfortunately

        @adapter_for(IOriginal)
        @implementer(ITarget)
        class Implementor(stuff):
            stuff

    .. python::
        from zope.interface import implementer

        @adapter_for(IOriginal, ITarget1, ITarget2, ITargetNotImplemented)
        @implementer(ITarget1)
        @implementer(ITarget2)
        @implementer(INotTarget)
        class Implementor(stuff):
            stuff
    """
    def _decorator(implementor): #pylint: disable=C0111
        register(implementor, orig, *target_interfaces)
        return implementor
    return _decorator

def deregister(implementor, orig, *target_interfaces):
    "exact opposite of register()"
    if not target_interfaces:
        target_interfaces = tuple(implementedBy(implementor))
    register(None, orig, *target_interfaces)


def lookup(targetinterface, obj):
    "look up to see if there are any adapters to adapt an obj to a targetinterface"
    try:
        sourceinterface = fakeimplementeds[type(obj)]
    except KeyError:
        sourceinterface = providedBy(obj)

    implementor = registry.lookup1(sourceinterface, targetinterface, '')

    if implementor == None:
        return None

    return implementor(obj)
adapter_hooks.append(lookup)