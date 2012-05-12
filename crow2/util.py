"""
A dropbox for uncategorized utility code that doesn't belong anywhere else.
"""

import warnings
import inspect
import functools

def paramdecorator(decorator_func):
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
    """
    args = inspect.getargspec(decorator_func).args
    if args[0] == "self":
        arg_target = 1
    else:
        arg_target = 0
    funcname = args[arg_target]
    @functools.wraps(decorator_func)
    def meta_decorated(*args, **keywords):
        "I'm tired of providing nonsense docstrings to functools.wrapped functions just to shut pylint up"
        if funcname in keywords:
            # a way for callers to force a normal function call
            func = keywords[funcname]
            del keywords[funcname]
            newargs = list(args)
            newargs.insert(arg_target, func)
            return decorator_func(*newargs, **keywords)

        # called as a simple decorator
        if (len(args) == arg_target+1 and
            (inspect.isfunction(args[arg_target]) or inspect.isclass(args[arg_target]))
            and len(keywords) == 0):
            return decorator_func(*args)

        else: # called as an argument decorator
            @functools.wraps(decorator_func)
            def decorator_return(func):
                "shut up, pylint - don't you know what functools.wraps does?"
                newargs = list(args)
                newargs.insert(arg_target, func)
                return decorator_func(*newargs, **keywords)
            return decorator_return
    meta_decorated.undecorated = decorator_func
    return meta_decorated

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
