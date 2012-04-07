#TODO: document me

import inspect
import functools
from collections import namedtuple

from crow2.util import paramdecorator


class DictPopper(object):
    def __init__(self, d):
        self._d = _d

    def pop(self, key):
        try:
            ret = self._d[key]
        else:
            del self._d[key]
            return ret
    __getattr__ = pop

@paramdecorator
def yielding(func):
    pass

class AttrDict(dict):
    __slots__ = ()
    __getattr__ = super(AttrDict).__getitem__
    __setattr__ = super(AttrDict).__setitem__

Registration = namedtuple("Registration", ["target", "args", "keywords"])
MethodRegistration = namedtuple("MethodRegistration", ["hook", "args", "keywords"])

class SortGroup(object):
    def __init__(self, registrations, before, after, tag):
        self.registrations = registrations
        self.before = before
        self.after = after
        self.tag = tag

class DependencyReference(object):
    def __init__(self, )

class Hook(object):
    """
    Contains the registration methods that are called to register a hook
    """
    def __init__(self):
        self.sorted_call_list = None
        self.registrations = {}

    ### Firing ------------------------------------------

    def fire(self, *args, **keywords):
        """
        Fire the hook. Ensures call list is sorted and calls everything.
        """
        if self.sorted_call_list == None:
            self.sorted_call_list = self._build_call_list(self.registrations)
        callargs, callkeywords = self._make_calltuple(*args, **keywords)
        self._fire_call_list(self.sorted_call_list, *callargs, **callkeywords)

    def _make_callargs(self, *dicts, **keywords):
        """
        Prepare the objects which will be passed into handlers
        """
        calldict = AttrDict()
        for d in dicts:
            calldict.update(d)
        calldict.update(keywords)
        return (calldict,), {}

    def _fire_call_list(self, calllist, *args, **keywords):
        for handler in calllist:
            handler(*args, **keywords)

    ### Baking/fire preparation -------------------------

    def _build_call_list(self, registrations):

        

    ### Registration ------------------------------------
    def register(self, func, *args, **keywords):
        self.sorted_call_list = None # need to recalculate
        self.registrations[func] 


    '''
    __call__ = paramdecorator(register)

    @paramdecorator
    def once(self, func, *args, **keywords):


    @paramdecorator
    def method(self, func, *args, **keywords):
        """
        Mark a method for registration later
        """
        try:
            registrations = func._method_registrations
        except AttributeError:
            registrations = []
            func._method_registrations = registrations
        reg = MethodRegistration(func, args, keywords)
        registrations.append(reg)'''

class InstantiationError(Exception):
    "thrown when ClassRegistrarMixin fails to instantiate a class"

class ClassRegistrarMixin(object):
    def __init__(self):
        self._class_registrations = []
        self._instances = []

    @paramdecorator
    def instantiate(self, cls, *args, **keywords):
        self.classes.add(Registration(cls, args, keywords))

    @paramdecorator
    def use_super(self, func, type):
        if type in ("none", "recurse", "normal"):
            func._super = type
        else:
            raise Exception("valid arguments for use_super() are 'none', 'recurse', or 'normal'")

    def _getreg(self, method):
        try:
            return method._method_registrations
        except:
            return []

    def _do_instantiation(self):
        for registration in self._class_registrations:
            flattened_dict = {}
            resolved_mro = inspect.getmro(registration.target)
            for cls in reversed(resolved_mro):
                flattened_dict.update(cls.__dict__)

            init = flattened_dict["__init__"]
            if self._getreg(init):
                if getattr(init, "_super", "none") != "none"
                    raise InstantiationError("__init__ may not use_super: %r.%r" %
                        (registration.target, init))
                def delayed_instantiate(*args, **keywords):
                    
                initreg = self._getreg(init)

class HookCategory(object):
    """
    Contains hooks or hookcategories. children can be accessed as attributes.
    """
    def __init__(self):
        self.children = {}

    def __getattr__(self, attr):
        try:
            return self.children[attr]
        except KeyError:
            raise AttributeError

    def _prepare(self):
        for child in children.values():
            try:
                prepare = child._prepare
            except AttributeError:
                continue
            prepare()

    def __setitem__(self, item, value):
        self.children[item] = value
