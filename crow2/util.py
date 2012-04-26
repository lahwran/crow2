"""
A dropbox for uncategorized utility code that doesn't belong anywhere else.
"""

import warnings
import inspect
import functools

def paramdecorator(decorator_func):
    if inspect.getargspec(decorator_func).args[0] == "self":
        arg_target = 1
    else:
        arg_target = 0
    @functools.wraps(decorator_func)
    def meta_decorated(*args, **keywords):
        if "func" in keywords:
            # a way for callers to force a normal function call
            func = keywords["func"]
            del keywords["func"]
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
        warnings.warn_explicit("Call to deprecated function %s: %s." % (func.__name__, reason),
                      category=DeprecationWarning,
                      filename=func.func_code.co_filename,
                      lineno=func.func_code.co_firstlineno + 1)
        return func(*args, **kwargs)
    return new_func

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

class ExceptionWithMessage(Exception):
    def __init__(self, *args, **kwargs):
        Exception.__init__(self, self.__class__.__doc__.format(*args, **kwargs))
