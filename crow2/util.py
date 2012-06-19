"""
A dropbox for uncategorized utility code that doesn't belong anywhere else.
"""

import warnings
import inspect
import functools
from collections import deque
from zope.interface import alsoProvides

class DecoratorPartial(object):
    def __init__(self, func, argnum, partialiface, include_call_type, args, keywords):
        self.func = func
        self.args = args
        self.keywords = keywords
        self.argnum = argnum
        if partialiface:
            alsoProvides(self, partialiface)
        self.partialiface = partialiface
        self.include_call_type = include_call_type


    def __call__(self, target):
        args = self.args[:self.argnum] + (target,) + self.args[self.argnum:]
        keywords = self.keywords
        if self.include_call_type:
            keywords["paramdecorator_simple_call"] = False

        return self.func(*args, **keywords)

    def copy(self):
        return DecoratorPartial(self.func, self.argnum, self.partialiface, self.include_call_type, self.args, self.keywords)


def paramdecorator(decorator_func, argname=None, argnum=None, useself=None, partialiface=None, include_call_type=False):
    """
    Paramater-taking decorator-decorator; That is, decorate a function with this to make it into a paramater-decorator

    Use of the paramdecorator decorator:

    Takes no special arguments; simply call as @paramdecorator. The first non-'self' argument of the decorated function
    will be passed the function or class that the produced decorator is used to decorate. The first non-self argument
    can also be passed as a keyword argument to the returned decorator, which will make it behave like a normal function.
    for this reason it is strongly recommended that you name your first argument "target", "func", or "clazz"
    (depending on what you accept).

    Use of produced parameter decorators:

    The produced decorator can be called either as @decorator with no arguments, or @decorator() with any arguments.
    When called with only a builtin-type callable as an argument (as in the case of @decorator), it will assume
    that it is being called with no arguments. When called with more arguments or when the first argument is not
    a callable, it will assume it is being called with multiple arguments and return a closure'd decorator.

    If you wish to force a parameter decorator to take the target function or class in the same call as arguments,
    then give it a keyword argument of the function's target name.

    Note: if the decorated decorator uses *args, you must provide argname and optionally one of argnum or useself.
    argname may only be used on its own when the function will accept the target as a kwarg.
    """
    if useself is not None:
        if argnum is not None:
            raise Exception("useself and argnum both do the same thing; they cannot be used at the same time")
        argnum = 1 if useself else 0

    if argnum is None and argname is None:
        args = inspect.getargspec(decorator_func).args
        if args[0] == "self":
            argnum = 1
        else:
            argnum = 0
        argname = args[argnum]
    elif argnum is not None and argname is None:
        args = inspect.getargspec(decorator_func).args
        argname = args[argnum]
    elif argnum is None and argname is not None:
        args = inspect.getargspec(decorator_func).args
        for index, name in enumerate(args):
            if name == argname:
                argnum = index
                break
        else:
            raise Exception("argname must point to an arg that exists")
    else:
        pass # if both are provided, we're good
    
 
    assert argnum is not None

    makepartial = functools.partial(DecoratorPartial, decorator_func, argnum, partialiface, include_call_type)

    @functools.wraps(decorator_func)
    def meta_decorated(*args, **keywords):
        "I'm tired of providing nonsense docstrings to functools.wrapped functions just to shut pylint up"
        if argname in keywords:
            # a way for callers to force a 'normal' function call
            arg = keywords[argname]
            del keywords[argname]
            preparer = makepartial(args, keywords)
            return preparer(arg)

        # called as a simple decorator
        if (len(args) == argnum+1 and
            (inspect.isfunction(args[argnum]) or
                inspect.isclass(args[argnum]) or
                inspect.ismethod(args[argnum]))
            and len(keywords) == 0):
            if include_call_type:
                return decorator_func(*args, paramdecorator_simple_call=True)
            else:
                return decorator_func(*args)
        else: # called as an argument decorator
            return makepartial(args, keywords)
    meta_decorated.undecorated = decorator_func
    return meta_decorated
paramdecorator = paramdecorator(paramdecorator) # we are ourselves!

@paramdecorator(argname="method_func", argnum=0)
class MethodProvides(object):
    def __init__(self, method_func, *interfaces):
        self.method_func = method_func
        functools.update_wrapper(self, method_func)
        self.interfaces = interfaces

    def __get__(self, instance, owner):
        result = self.method_func.__get__(instance, owner)
        self.alsoProvides(result, *self.interfaces)
        return result

    def __call__(self, *args, **keywords):
        raise TypeError("MethodProvides for method %r cannot be called directly" % (self.method_func))

@paramdecorator
def deprecated(func, reason="deprecated"):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.

    from http://wiki.python.org/moin/PythonDecoratorLibrary#Generating_Deprecation_Warnings
    """
    @functools.wraps(func)
    def new_func(*args, **kwargs):
        'shut up, pylint'
        warnings.warn_explicit("Call to deprecated function %s: %s." % (func.__name__, reason),
                      category=DeprecationWarning,
                      filename=func.func_code.co_filename,
                      lineno=func.func_code.co_firstlineno + 1)
        return func(*args, **kwargs)
    return new_func

'''
class EnumElement(object):
    def __init__(self, owner, index, name):
        self.index = index
        self.name = name
        self.owner = owner

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.owner.name + "." + self.name

class Enum(object):

    def __init__(self, enumname, *lookup):
        self.name = enumname
        lookup = list(lookup)
        self.lookup = lookup
        for index, item in enumerate(lookup):
            lookup[index] = EnumElement(enumname, index, item)
            setattr(self, item, lookup[index])

    def __repr__(self):
        return "Enum(%r)" % self.name
'''

class ExceptionWithMessage(Exception):
    """
    Subclass this class and provide a docstring; the docstring will be
    formatted with the __init__ args and then used as the error

    (if you are seeing this as a result of an exception, someone - possibly you  - forgot
        to provide a subclass with a docstring!)
    """
    def __init__(self, *args, **kwargs):
        assert self.__class__ != ExceptionWithMessage
        Exception.__init__(self, self.__class__.__doc__.format(*args, **kwargs))

class KeyAttributeCollisionError(ExceptionWithMessage):
    """Key {1!r} collides with attribute of the same name on AttrDict it is set in """

class AttrDict(dict):
    """
    Dict with it's values accessible as attributes
    """
    def __init__(self, *args, **keywords):
        dict.__init__(self, *args, **keywords)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError

    def __setattr__(self, name, attr):
        self[name] = attr

    def __repr__(self):
        return "AttrDict(%s)" % super(AttrDict, self).__repr__() #pragma: no cover
