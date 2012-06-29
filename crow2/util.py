"""
A dropbox for uncategorized utility code that doesn't belong anywhere else.
"""

import warnings
import inspect
import functools
import os
from collections import deque

from twisted.python.reflect import fullyQualifiedName
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

    '''
    def setdefault(self, name, value, update=True):
        if update:
            try:
                oldvalue = self[name]
            except KeyError:
                self[name] = value
            else:
                to_update = deque([(oldvalue, newvalue)])
                while to_update:
                    target, source = to_update.pop_left()
                    if isinstance(target, dict) and isinstance(source, dict):
                        for key in source:
                            if key not in target:
                                target[key] = source[key]
                            else:
                                to_update.append((target[key], source[key]))
        else:
            return dict.setdefault(self, name, value)
    '''

    def __repr__(self):
        return "AttrDict(%s)" % super(AttrDict, self).__repr__() #pragma: no cover

DEBUG = "CROW2_DEBUG" in os.environ

def DEBUG_calling_name(): #pragma: no cover
    if not DEBUG:
        # TODO: print warning if this code is run
        return "<**CROW2_DEBUG not in environment**>"

    stackframe = inspect.stack()[2] # 0 = us, 1 = who called us, 2 = who called them
    frame = stackframe[0]
    code_name = frame.f_code.co_name

    module = inspect.getmodule(frame)
    modulename = fullyQualifiedName(module)

    return modulename + '.' + code_name
