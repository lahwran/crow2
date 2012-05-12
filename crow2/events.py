#!/usr/bin/python
"""
Message-passing "event" system
"""
#TODO: double-check documentation

import inspect
import functools
import types
from twisted.python.reflect import namedAny
from twisted.python import log
from collections import defaultdict

from crow2.util import paramdecorator, ExceptionWithMessage
from crow2.toposort import topological_sort
#TODO: from crow2.adapterutil import adapter_for
from zope.interface import Interface, implementer, Attribute


@paramdecorator
def yielding(func):
    """
    my own implementation of basically the same thing twisted.defer.inlineCallbacks does, except
    with crow2 goodness

    note: if a yielded hook is garbage collected without being fired, then the generator
    will be lost without continuing
    """
    @functools.wraps(func)
    def proxy(*args, **keywords):
        "proxy callable which will automatically initialize an IteratorCallbacks instance for the generator"
        generator = func(*args, **keywords)
        callback_manager = _IteratorCallbacks(generator, func)
        return callback_manager
    return proxy

#class SingleCallbackHook(Interface):
#    def __call__(callback):
#        "register a callback to be called once"

class _IteratorCallbacks(object):
    """
    Bulk of yielding() implementation
    """
    def __init__(self, iterator, factory):
        self.iterator = iterator
        self.factory = factory
        self.call_position = 0
        self.next()

    def next(self, to_send=None):
        "get the next hook from the iterator and register a one-use callback to it"
        try:
            if to_send == None:
                yielded = self.iterator.next()
            else:
                yielded = self.iterator.send(to_send)
        except StopIteration:
            log.msg("generator stopping")
        else:
            callback = self.make_callback()
            #hook = SingleCallback(yielded)
            hook = yielded
            hook.once(callback)
    send = next

    def make_callback(self):
        "produce a callback which can only be called once"
        next_call_position = self.call_position + 1
        @functools.wraps(self.factory)
        def callback(*args, **keywords):
            "callback which will check that it's called at the right time"
            self.call_position += 1
            assert self.call_position == next_call_position

            self.next(CallArguments(args, keywords))
        callback.__name__ += "/%d" % next_call_position # pylint: disable=E1101
        return callback


class CallArguments(object):
    """
    Represents the arguments of a call such that they can be accessed in a familiar way

    allows accessing keyword arguments as attributes and items; allows accessing positional arguments
    as items.
    """
    def __init__(self, positional, keywords): #, names=None):
        #TODO: allow yielding of naming information to simulate a function definition
        self.positional = tuple(positional)
        self.keywords = dict(keywords)

    def __hash__(self, other):
        raise TypeError("unhashable type: 'Arguments'")

    def __eq__(self, other):
        try:
            return other.positional == self.positional and other.keywords == self.keywords
        except AttributeError:
            return False

    def __iter__(self):
        return self.positional.__iter__()

    def __repr__(self):
        return "Arguments(%r, %r)" % (self.positional, self.keywords)

    def __getattr__(self, attr):
        try:
            return self.keywords[attr]
        except KeyError:
            raise AttributeError("No such attribute or named argument - did you try to use a "
                                "single-arg callback, but forget to do `thisobject, = yield ...`?")

    def __getitem__(self, item):
        try:
            return self.positional[item]
        except TypeError:
            return self.keywords[item]

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

class MethodRegistration(object):
    """
    Data structure used by class instantiation and method registration
    """
    def __init__(self, hook, args, keywords):
        self.hook = hook
        self.args = args
        self.keywords = keywords

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

# long exception names are fun /s
class DependencyMissingError(ExceptionWithMessage):
    "{0!r}: Could not resolve dependency {1!r} of dep-res node {2!r}"

class DuplicateRegistrationError(Exception):
    "Handler[s] was/were already registered, but something tried to register them again"

class InvalidOrderRequirementsError(ExceptionWithMessage):
    "{0!r} registered to {1!r} with both tag and dependency"

class NotRegisteredError(Exception):
    "Raised when an unregister is attempted for a registration which is not registered"

class NameResolutionError(Exception):
    "Raised when dependency resolution fails to locate an appropriate handler with a provided name"

class NotInstantiableError(Exception):
    "Raised when a class registered for instantiation cannot be instantiated"

class AlreadyRegisteredError(Exception):
    "Raised when a registration is attempted on an object which is already registered"

class MethodProxy(object):
    """
    Method proxy - multiplexes a single method to all bound methods that have been created by
    a ClassRegistration
    """
    def __init__(self, clazz, name, methodfunc, regs):
        self.clazz = clazz
        self.name = name
        self.methodfunc = methodfunc
        self.unbound = getattr(clazz, name)
        self.registrations = regs

        self._proxy_for = (self.methodfunc, self.unbound)

        self.hooks_registered = []

        self.bound_methods = []
        self.instances_to_methods = {}

    def register(self):
        """
        register this method proxy with all hooks that the method was attached to
        """
        if self.hooks_registered:
            raise AlreadyRegisteredError(repr(self))

        for registration in self.registrations:
            hook = registration.hook
            hook.register(self, *registration.args, **registration.keywords)
            self.hooks_registered.append(hook)

    def unregister(self):
        """
        unregister this method proxy from it's hooks
        """
        if not self.hooks_registered:
            raise NotRegisteredError(repr(self))

        for hook in self.hooks_registered:
            hook.unregister(self)
        self.hooks_registered = []

    def add_bound_method(self, instance):
        """
        register a bound method for an instance of the class this proxy's method belongs to
        """
        bound_method = getattr(instance, self.name)
        instance_id = id(instance)
        if instance_id in self.instances_to_methods:
            raise AlreadyRegisteredError("%r (id: %r) to %r" % (instance, instance_id, self))
        self.instances_to_methods[instance_id] = bound_method
        self.bound_methods.append(bound_method)

    def remove_bound_method(self, instance):
        """
        remove a bound method belonging to the provided instance; instance must have a bound method registered with
        this proxy
        """
        instance_id = id(instance)
        try:
            bound_method = self.instances_to_methods[instance_id]
        except KeyError:
            raise NotRegisteredError("%r (id: %r) to %r" % (instance, instance_id, self))
        else:
            del self.instances_to_methods[instance_id]
            # bad time complexity, but I expect that the datasets will be small,
            # so the overhead is preferable; if people use this for large numbers
            # of class instantiations of the same class to the same hook, then
            # this will need to be changed to a data structure which can handle
            # that; I'm doing this because I don't off the top of my head know
            # what will have equivalent overhead but better time complexity
            self.bound_methods.remove(bound_method)

    def __call__(self, *args, **keywords):
        """
        pass along a call to all bound methods
        """
        for bound_method in self.bound_methods:
            bound_method(*args, **keywords)

    @classmethod
    def _get_method_regs(cls, method):
        """
        helper to retrieve the method registrations from a provided method function
        """
        try:
            return method._crow2events_method_regs_
        except AttributeError:
            return []

    def __repr__(self):
        return "MethodProxy(%s.%s.%s)" % (self.clazz.__module__, self.clazz.__name__,
                                            self.name)

class ClassRegistration(object):
    """
    Proxies a class such that when an instance is __call__ed, the created instance will be tracked and
    any @hook.method-ed methods will be registered
    """
    def __init__(self, hook, clazz):
        self.clazz = clazz
        flattened = AttrDict()
        self.flattened = flattened
        resolved_mro = inspect.getmro(clazz)
        for parentclass in reversed(resolved_mro):
            flattened.update(parentclass.__dict__)

        self._proxy_for = (clazz,)
        self.hook = hook

        init = flattened['__init__']
        if MethodProxy._get_method_regs(init):
            raise NotInstantiableError("%r: cannot register class %r for instantiation with listening __init__" % 
                                        (self, clazz))

        self.method_proxies = set()
        self.proxies_registered = False
        for name, attribute in flattened.items():
            reg = MethodProxy._get_method_regs(attribute)
            if reg:
                self.method_proxies.add(MethodProxy(clazz, name, attribute, reg))

        self.instances = {}

    def register_proxies(self):
        """
        register all method proxies with their respective hooks
        """
        for proxy in self.method_proxies:
            proxy.register()
        self.proxies_registered = True

    def unregister_proxies(self):
        """
        unregister all method proxies
        """
        for proxy in self.method_proxies:
            proxy.unregister()
        self.proxies_registered = False

    def __call__(self, *call_args, **call_keywords):
        """
        Instantiate our class and begin tracking it

        1. instantiate the class
        2. add the instance to all of our method proxies
        3. shove a callback into the instance to allow it to ask us to delete it
        4. return the created instance
        """
        instance = self.clazz(*call_args, **call_keywords)
        instance_id = id(instance)

        if not len(self.instances):
            if self.proxies_registered:
                raise AlreadyRegisteredError("%r: about to register proxies, but proxies "
                            "are registered, and no previous instances known!" % self)
            self.register_proxies()

        self.instances[instance_id] = instance
        for proxy in self.method_proxies:
            proxy.add_bound_method(instance)

        if hasattr(instance, "parent_registration"):
            log.msg("WARNING: about to obliterate instance %r's attribute parent_registration"
                               " with %r!" % (instance, self))
        instance.parent_registration = self
        @functools.wraps(self.free_instance)
        def delete():
            "This docstring to shut pylint up"
            self.free_instance(instance)
        if hasattr(instance, "delete"):
            log.msg("WARNING: about to obliterate instance %r's attribute delete"
                               " with %r!" % (instance, delete))
        instance.delete = delete
        return instance


    def free_instance(self, instance):
        """
        Release an instance

        Unregister the instance from all method proxies so that it won't get called back anymore, and then free it
        from the class proxy so that it can be garbage collected
        """
        instance_id = id(instance)
        if instance_id not in self.instances:
            raise NotRegisteredError("%r: instance %r (id: %r) is not registered" % (self, instance, instance_id))

        del self.instances[instance_id]

        for proxy in self.method_proxies:
            proxy.remove_bound_method(instance)

        if not len(self.instances):
            if not self.proxies_registered:
                raise NotRegisteredError("%r: about to unregister proxies, but proxies are already "
                                        "unregistered, and all instances already unregistered!" % self)
            self.unregister_proxies()



class Hook(object):
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
        callargs, callkeywords = self._make_callargs(*args, **keywords)
        self._fire_call_list(self.sorted_call_list, *callargs, **callkeywords)

        return callargs[0]

    def _make_callargs(self, *dicts, **keywords):
        """
        Prepare the objects which will be passed into handlers
        """
        calldict = AttrDict()
        for context_dict in dicts:
            calldict.update(context_dict)
        calldict.update(keywords)
        calldict.update({"calling_hook": self})
        return (calldict,), {}

    def _fire_call_list(self, calllist, *args, **keywords):
        """
        actually call all the handlers in our call list
        """
        # TODO: exception handling
        # TODO: cancel-handling hook subclass
        for handler in calllist:
            #try:
            handler(*args, **keywords)
            #except:
            #    log.err()
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


    # these two are separate so that overriding register_* in subclasses will work as expected
    # they need to be separate attributes because paramdecorator-ized funcs behave very unexpectedly
    # when called as normal functions
    @paramdecorator
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

    def register_instantiation(self, clazz, *reg_args, **reg_keywords):
        """
        Register a class for instantiation; registers the provided class through a ClassRegistration proxy
        """
        self.register(ClassRegistration(self, clazz), *reg_args, **reg_keywords)

        return clazz

    @paramdecorator
    def instantiate(self, cls, *args, **keywords):
        """
        decorator version of register_instantiation
        """
        return self.register_instantiation(cls, *args, **keywords)

class HookCategory(object): #TODO: make this do stuff
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
        "TODO: what was I doing here again?"
        for child in self.children.values():
            try:
                prepare = child._prepare
            except AttributeError:
                continue
            prepare()

    def __setitem__(self, item, value):
        self.children[item] = value

# '''
