from zope.interface import Interface, Attribute, implementer
from crow2.util import AttrDict
import functools
import types
from twisted.python.reflect import namedAny
from twisted.python import log
from collections import defaultdict
from crow2.util import paramdecorator
from .toposort import topological_sort
from .exceptions import (NameResolutionError, NotRegisteredError, DuplicateRegistrationError,
        InvalidOrderRequirementsError, DependencyMissingError)

class IRegistrationContainer(Interface):
    """
    A container that can be sorted by Hook's dependency sort and then resolved to some handlers
    """
    targets = Attribute("a set of all targets contained")
    before = Attribute("an iterable of all things this should be before")
    after = Attribute("an iterable of all things this should be after")

@implementer(IRegistrationContainer)
class SingleRegistration(object):
    """
    Container for a single registration
    """
    _is_taggroup = False
    def __init__(self, target, before, after):
        self.target = target
        self.before = before
        self.after = after

    @property
    def targets(self):
        """
        Returns a list of 
        """
        return set((self.target,))

    def __repr__(self):
        return "SingleRegistration(%r)" % self.target

class TagDict(dict):
    """
    Defaultdict-like dict which creates a TaggedGroup with the context of the dict and key.
    Oh, and it automatically saves the key if it's referenced at all, too.
    """
    def __missing__(self, key):
        value = TaggedGroup(key, self)
        self[key] = value
        return value

@implementer(IRegistrationContainer)
class TaggedGroup(object):
    """
    Container for a group of registrations tagged with a name
    """
    _is_taggroup = True
    def __init__(self, name, parent):
        self.name = name
        self._parent = parent
        self.before = ()
        self.after = ()
        self.targets = set()
        self.deletable = True

    def add(self, target):
        "add a target handler"
        self.targets.add(target)

    def remove(self, target):
        "remove a target handler"
        self.targets.remove(target)
        if not len(self.targets) and self.deletable:
            del self._parent[self.name]

    def dependencies(self, before, after):
        """
        set the dependencies, overwriting any that may have been there before
        """
        #TODO: this needs to assert that there were none there before
        self.before = before
        self.after = after
        self.deletable = False

    def __repr__(self):
        return "<Tag:%s>" % self.name # pragma: no cover

class MethodRegistration(object):
    """
    Data structure used by class instantiation and method registration
    """
    def __init__(self, hook, args, keywords):
        self.hook = hook
        self.args = args
        self.keywords = keywords

class IHook(Interface):
    def register(target, **keywords):
        """
        Register a callable to be called by this hook.
        The callable must take at least one argument and
        have no more than one required arguments.
        """
    def register_once(target, **keywords):
        """
        Register a callable to be called by this hook and then unregistered
        """
    def register_method(target, **keywords):
        """
        Add a registration to a target method such that it can be detected by ClassRegistration
        """
    def unregister(target):
        """
        Unregister a callable from this hook
        """
    def fire(*contexts, **arguments):
        """
        Call all handlers associated with this hook.
        Each positional argument must be a dictionary; each
        keyword argument is added to any dictionaries to form the
        event passed into the handlers.
        """

class IDecoratorHook(IHook): # pragma: no cover
    def __call__(**keywords):
        "Create an IPartialHook for register()"

    def once(**keywords):
        "Create a partial for register_once()"

    def method(**keywords):
        "Create a partial for register_method()"

class IPartialRegistration(Interface):
    func = Attribute("the method-function which this partial is for")
    args = Attribute("the list of arguments passed to create partial. 0 is self.")
    def __call__(target):
        """
        Complete registration with this target
        """
    def copy():
        "Return a full copy of this partial"

@implementer(IHook)
class BaseHook(object):
    """
    Contains the registration methods that are called to register a hook

    To create a hook, simply instantiate this class. if you want to customize your hook, subclass this class.
    It's designed to be highly subclassable. Be sure to read all the docs and preferably a large amount of the code
    before you start subclassing; a lot is already provided.
    """
    def __init__(self, default_tags=()):
        self.sorted_call_list = None
        self.handler_references = {}
        self.references = {}
        self.referencenames = {}
        self.registration_groups = set()
        self.tags = TagDict()

        lasttag = ()
        for tagname in default_tags:
            self.tags[tagname].dependencies((), lasttag)
            lasttag = (self.tags[tagname],)

        self._toposort = []

    ### Firing ------------------------------------------

    def fire(self, *args, **keywords):
        """
        Fire the hook. Ensures call list is sorted and calls everything.
        """

        if self.sorted_call_list == None:
            self._toposort, self.sorted_call_list = self._build_call_list(self.registration_groups)
        event = self._make_eventobj(*args, **keywords)
        self._fire_call_list(self.sorted_call_list, event)

        return event

    def _make_eventobj(self, *dicts, **keywords):
        """
        Prepare the objects which will be passed into handlers
        """
        event = AttrDict()
        for context_dict in dicts:
            event.update(context_dict)
        event.update(keywords)
        event.update({"calling_hook": self})
        return event

    def _fire_call_list(self, calllist, event):
        """
        actually call all the handlers in our call list
        """
        # TODO: exception handling
        # TODO: cancel-handling hook subclass
        for handler in calllist:
            try:
                handler(event)
            except:
                log.err()
                # derp, what now

    ### Baking/fire preparation -------------------------

    def _get_name(self, obj):
        """
        Attempt to determine what an object's fully qualified name is. If we can't find one,
        NameResolutionError is raised.
        """
        cachename = '_crow2events_fully_qualified_name_'

        try:
            result = getattr(obj, cachename)
        except AttributeError:
            pass

        if type(obj) == types.MethodType:
            return '.'.join((obj.__module__, obj.im_class.__name__, obj.__name__))
        elif type(obj) in (type, types.ClassType, types.FunctionType):
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
                log.msg("WARNING: name resolved to different object: %r -> %r -> %r" % # pragma: no cover
                        (obj, result, resolved_obj))
        try:
            setattr(obj, cachename, result)
        except AttributeError: # shouldn't normally happen, so: pragma: no cover
            pass # cannot cache
        return result


    def _lookup_strdep(self, node, dep):
        """
        Search the things this hook knows about for a string representing a dependency

        checks:

        0. check if it's explicitly a tag; if so, skip 1 and 2
        1. Check to see if we know about anything from the same file which matches
        2. Check to see if we know about anything from a neighboring file which matches
        3. Check to see if we have a tag by the name
        4. error
        """
        if not node._is_taggroup and not dep.startswith(":"):
            # relative/local
            depsplit = dep.split(".")
            namesplit = self._get_name(node.target).split(".")
            for steps_up in (1, 2):
                relative_dep = ".".join(namesplit[:-steps_up] + depsplit)
                try:
                    return self.referencenames[relative_dep]
                except KeyError:
                    pass

            # absolute
            try:
                return self.referencenames[dep]
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
        """
        Resolve a dependency

        1. if it's a string reference, look it up
        2. if we have any known proxies for the found object, use those instead of the object itself
        """
        if type(dep) == str:
            registration = self._lookup_strdep(node, dep)
        elif hasattr(dep, "_is_taggroup"):
            return dep
        else:
            handler = self.references[dep]
            registration = self.handler_references[handler]
        return registration

    def _build_call_list(self, registrations):
        """
        Sort the call list by dependencies and expand each registration group's targets
        """
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
    def _ensure_list(self, deplist):
        """
        wrap provided argument in a list if it isn't already one.
        """
        if type(deplist) not in (list, tuple, set):
            return (deplist,)
        else:
            return tuple(deplist)

    def register(self, func, **keywords):
        """
        Register an object as a handler, with any keywords you might like
        """
        # Note: keywords.get is used because register(func, "name") would be ambiguous
        before = self._ensure_list(keywords.get("before", tuple()))
        after = self._ensure_list(keywords.get("after", tuple()))
        tag = keywords.get("tag", None)

        if tag and (len(before) or len(after)):
            raise InvalidOrderRequirementsError(func, self)

        try:
            references = func._proxy_for
        except AttributeError:
            references = [func]
        for reference in references:
            if reference in self.references:
                raise DuplicateRegistrationError("%r (%r) registered twice to hook %r" %
                        (reference, func, self))

        if tag:
            self.tags[tag].add(func)
            self.handler_references[func] = self.tags[tag]
        else:
            registration = SingleRegistration(func, before, after)
            self.handler_references[func] = registration

        for reference in references:
            self.references[reference] = func
            try:
                self.referencenames[self._get_name(reference)] = self.handler_references[func]
            except NameResolutionError:
                log.msg("WARNING: unable to determine name of object %r (%s, %r, %r)" %
                            (reference, str(reference), type(reference), dir(reference)))


        self.registration_groups.add(self.handler_references[func])

        self.sorted_call_list = None # need to recalculate

        return func

    def register_once(self, func, *reg_args, **reg_keywords):
        """
        Register a handler to be called once
        """
        #TODO: ensure that unregistration works if someone tries to unregister a register_once'd handler
        @functools.wraps(func)
        def unregister_callback(*call_args, **call_keywords):
            "this docstring to shut pylint up - nobody will ever see it except reading the code itself"
            try:
                return func(*call_args, **call_keywords)
            finally:
                self.unregister(unregister_callback)
        self.register(unregister_callback, *reg_args, **reg_keywords)
        return func

    def unregister(self, func):
        """
        Unregister a handler
        """
        try:
            references = func._proxy_for
        except AttributeError:
            references = [func]
        for reference in references:
            if reference not in self.references:
                raise NotRegisteredError("%r: cannot unregister %r (%r) as it is not registered" %
                        (self, reference, func))
        for reference in references:
            del self.references[reference]
            try:
                del self.referencenames[self._get_name(reference)]
            except NameResolutionError:
                log.msg("WARNING: unable to determine name of object %r (%s, %r, %r)" %
                            (reference, str(reference), type(reference), dir(reference)))

        registration = self.handler_references[func]
        del self.handler_references[func]
        if registration._is_taggroup:
            registration.remove(func)
        else:
            self.registration_groups.remove(registration)

        self.sorted_call_list = None

class DecoratorMixin(object):
    @paramdecorator(partialiface=IPartialRegistration)
    def __call__(self, func, *args, **keywords):
        """
        Decorator version of register()
        """
        return self.register(func, *args, **keywords)

    @paramdecorator
    def once(self, func, *args, **keywords):
        """
        Decorator version of register_once()

        TODO: who in the world would ever use a decorator to register once?
        """
        return self.register_once(func, *args, **keywords)

    @paramdecorator
    def method(self, func, *args, **keywords):
        """
        Mark a method for registration later

        ** DO NOT OVERRIDE IN A SUBCLASS unless you understand the
            class instantiation handler system well
            enough to understand the consequences! See MethodProxy and ClassRegistration **
        """
        try:
            method_regs = func._crow2events_method_regs_
        except AttributeError:
            method_regs = []
            func._crow2events_method_regs_ = method_regs
        reg = MethodRegistration(self, args, keywords)
        method_regs.append(reg)
        return func

@implementer(IDecoratorHook)
class DecoratorHook(BaseHook, DecoratorMixin):
    pass

from ._classreg import ClassregMixin

class Hook(DecoratorHook, ClassregMixin):
    pass

class CancellableHook(Hook):
    def _make_eventobj(self, *dicts, **keywords):
        event = super(CancellableHook, self)._make_eventobj(*dicts, **keywords)
        def cancel():
            event.cancelled = True
        event.cancelled = False
        event.cancel = cancel

    def _fire_call_list(self, calllist, event):
        for handler in calllist:
            try:
                handler(event)
            except:
                log.err()
            if event.cancelled:
                break
