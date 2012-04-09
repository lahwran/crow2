#TODO: document me

import inspect
import functools
import types
from twisted.python.reflect import namedAny
from collections import namedtuple, defaultdict

from crow2.util import paramdecorator
from crow2.toposort import topological_sort


@paramdecorator
def yielding(func):
    pass

class AttrDict(dict):
    def __getattr__(self, name):
        return self[name]

    def __setattr__(self, name, attr):
        self[name] = attr


MethodRegistration = namedtuple("MethodRegistration", ["hook", "args", "keywords"])

class SingleRegistration(object):
    _is_taggroup = False
    def __init__(self, target, before, after):
        self.target = target
        self.before = before
        self.after = after

    @property
    def targets(self):
        return set((self.target,))

class TagDict(dict):
    def __missing__(self, key):
        value = TaggedGroup(self, key)
        self[key] = value
        return value

class TaggedGroup(object):
    _is_taggroup = True
    def __init__(self, parent, name):
        self.name = name
        self._parent = parent
        self.before = ()
        self.after = ()
        self.targets = set()
        self.deletable = True

    def add(self, target):
        self.targets.add(target)

    def remove(self, target):
        self.targets.remove(target)
        if not len(self.targets) and self.deletable:
            del self._parent[self.name]

    def dependencies(self, before, after):
        self.before = before
        self.after = after
        self.deletable = False

    def __repr__(self):
        return "<Tag:%s>" % self.name # pragma: no cover

# long exception names are fun /s
class DependencyMissingError(Exception):
    def __init__(self, *args):
        Exception.__init__(self, "%r: Could not resolve dependency %r of dep-res node %r" % args)

class DuplicateRegistrationError(Exception):
    def __init__(self, *args):
        Exception.__init__(self, "%r registered twice to hook %r" % args)

class InvalidOrderRequirementsError(Exception):
    def __init__(self, *args):
        Exception.__init__(self, "%r registered to %r with both tag and dependency" % args)

class NotRegisteredError(Exception):
    def __init__(self, hook, func):
        Exception.__init__(self, "%r: cannot unregister %r as it is not registered" % (hook, func))

class NameResolutionError(Exception):
    pass

class Hook(object):
    """
    Contains the registration methods that are called to register a hook
    """
    def __init__(self, default_tags=()):
        self.sorted_call_list = None
        self.handlers = {}
        self.handlernames = {}
        self.registration_groups = set()
        self.tags = TagDict()

        lasttag = ()
        for tagname in default_tags:
            self.tags[tagname].dependencies((), lasttag)
            lasttag = (self.tags[tagname],)

    ### Firing ------------------------------------------

    def fire(self, *args, **keywords):
        """
        Fire the hook. Ensures call list is sorted and calls everything.
        """

        if self.sorted_call_list == None:
            self._toposort, self.sorted_call_list = self._build_call_list(self.registration_groups)
        callargs, callkeywords = self._make_callargs(*args, **keywords)
        self._fire_call_list(self.sorted_call_list, *callargs, **callkeywords)

        return callargs[0]

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
        # todo: exception handling
        # todo: cancel handling (should it be separate?)
        for handler in calllist:
            #try:
            handler(*args, **keywords)
            #except:
            #    assert not "left unfinished"
                # derp, what now

    ### Baking/fire preparation -------------------------

    def _get_name(self, obj):
        cachename = '_crow2events_fully_qualified_name_'

        try:
            result = getattr(obj, cachename)
        except AttributeError:
            pass

        if type(obj) == types.MethodType:
            return '.'.join((obj.__module__, obj.im_class.__name__, obj.__name__))
        elif type(obj) in (types.ClassType, types.FunctionType):
            result = obj.__module__ + "." + obj.__name__
        elif type(obj) == types.ModuleType:
            result = obj.__name__
        else:
            # should give a best effort before erroring
            raise NameResolutionError("cannot determine full qualified name for type %r" % type(obj))
        try:
            resolved_obj = namedAny(result) 
        except AttributeError:
            pass
        else:
            if resolved_obj is not obj:
                assert not 'left unfinished'
                # warn here
        try:
            setattr(obj, cachename, result)
        except AttributeError:
            pass # cannot cache
        return result


    def _lookup_strdep(self, node, dep):
        if not node._is_taggroup and not dep.startswith(":"):
            # relative/local
            depsplit = dep.split(".")
            namesplit = self._get_name(node.target).split(".")
            if len(depsplit) == 1: # no dots - local; go up 1
                up = 1
            else: # at least one dot; go up to the package level
                up = 2
            relative_dep = ".".join(namesplit[:-up] + depsplit)
            try:
                return self.handlernames[relative_dep]
            except KeyError:
                pass

            # absolute
            try:
                return self.handlernames[dep]
            except KeyError:
                pass

        if dep.startswith(":"): # starting a dependency with a colon ensures that it refers to a tag
            tag_dep = dep[1:]
        else:
            tag_dep = dep

        if tag_dep in self.tags: # don't want to create it if missing!
            return self.tags[tag_dep]

        raise DependencyMissingError(self, dep, node)

    def _resolve_dep(self, node, dep):
        if type(dep) == str:
            dep = self._lookup_strdep(node, dep)
        try:
            return self.handlers[dep]
        except KeyError:
            return dep

    def _build_call_list(self, registrations):
        # todo: expansion handling
        deptree = defaultdict(set)
        for reg_group in registrations:
            dependencies = deptree[reg_group]

            for dep in reg_group.after:
                dep = self._resolve_dep(reg_group, dep)
                dependencies.add(dep)

            for dep in reg_group.before:
                dep = self._resolve_dep(reg_group, dep)
                deptree[dep].add(reg_group)

        toposorted = topological_sort(deptree)
        result = []
        for reg_group in toposorted:
            result.extend(reg_group.targets)
        return toposorted, tuple(result)

    ### Registration ------------------------------------
    def _tuplize_dependency(self, deplist):
        "this needs a better name"
        if type(deplist) not in (list, tuple, set):
            return (deplist,)
        else:
            return tuple(deplist)

    def register(self, func, **keywords):
        if func in self.handlers:
            raise DuplicateRegistrationError(func, self)
        before = self._tuplize_dependency(keywords.get("before", tuple()))
        after = self._tuplize_dependency(keywords.get("after", tuple()))
        tag = keywords.get("tag", None)

        if tag and (len(before) or len(after)):
            raise InvalidOrderRequirementsError(func, self)
        elif tag:
            self.tags[tag].add(func)
            self.handlers[func] = self.tags[tag]
        else:
            registration = SingleRegistration(func, (before),
                                        self._tuplize_dependency(after))
            self.handlers[func] = registration
        
        self.registration_groups.add(self.handlers[func])

        self.sorted_call_list = None # need to recalculate

        try:
            self.handlernames[self._get_name(func)] = self.handlers[func]
        except NameResolutionError:
            assert not "left unfinished"
            # NEED LOGGING WAT DO
            # do not correct this syntax error until a logging solution is assembled
            # twisted logging was cool iirc

        return func

    def register_once(self, func, *reg_args, **reg_keywords):
        @functools.wraps(func)
        def deregister(*call_args, **call_keywords):
            try:
                return func(*call_args, **call_keywords)
            finally:
                self.deregister(deregister)
        self.register(deregister, *reg_args, **reg_keywords)
        return func

    def deregister(self, func):
        if func not in self.handlers:
            raise NotRegisteredError(self, func)
        registration = self.handlers[func]
        del self.handlers[func]
        if registration._is_taggroup:
            registration.remove(func)
        else:
            self.registration_groups.remove(registration)

        try:
            del self.handlernames[self._get_name(func)]
        except NameResolutionError:
            assert not "left unfinished"

        self.sorted_call_list = None


    # these three are separate so that overriding register_* in subclasses will work as expected
    # they need to be separate attributes because paramdecorator-ized funcs behave very unexpectedly
    # when called as normal functions
    @paramdecorator
    def __call__(self, func, *args, **keywords):
        return self.register(func, *args, **keywords)

    @paramdecorator
    def once(self, func, *args, **keywords):
        return self.register_once(func,*args, **keywords)

    @paramdecorator
    def method(self, func, *args, **keywords):
        """
        Mark a method for registration later

        ** DO NOT OVERRIDE unless you understand the
            class instantiation handler system well
            enough to understand the consequences! **
        """
        try:
            method_regs = func._crow2events_method_regs_
        except AttributeError:
            registrations = []
            func._crow2events_method_regs_ = registrations
        reg = MethodRegistration(func, args, keywords)
        method_regs.append(reg)


class InstantiationError(Exception):
    "thrown when ClassRegistrarMixin fails to instantiate a class"

'''
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
'''