#!/usr/bin/python
#TODO: document me

import inspect
import functools
import types
from twisted.python.reflect import namedAny
from twisted.python import log
from collections import namedtuple, defaultdict

from crow2.util import paramdecorator
from crow2.toposort import topological_sort
from crow2.adapterutil import adapter_for


@paramdecorator
def yielding(func):
    """
    my own implementation of basically the same thing twisted.defer.inlineCallbacks does, except
    with crow2 goodness

    note: if a yielded callback is garbage collected without being fired, then the generator
    will be lost without continuing
    """
    @functools.wraps(func)
    def proxy(*args, **keywords):
        generator = func(*args, **keywords)
        callback_manager = IteratorCallbacks(generator)
        callback_manager.first()
        return callback_manager
    return proxy



class IteratorCallbacks(object):
    def __init__(self, iterator):
        self.iterator = iterator
        self.register_next()

    def register_next(self):
        pass

    def callback(self, *args, **keywords):
        pass



class AttrDict(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError

    def __setattr__(self, name, attr):
        self[name] = attr

    def __repr__(self):
        return "AttrDict(%s)" % super(AttrDict, self).__repr__() #pragma: no cover

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

    def __repr__(self):
        return "SingleRegistration(%r)" % self.target

class TagDict(dict):
    def __missing__(self, key):
        value = TaggedGroup(key, self)
        self[key] = value
        return value

class TaggedGroup(object):
    _is_taggroup = True
    def __init__(self, name, parent):
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
    pass

class InvalidOrderRequirementsError(Exception):
    def __init__(self, *args):
        Exception.__init__(self, "%r registered to %r with both tag and dependency" % args)

class NotRegisteredError(Exception):
    pass

class NameResolutionError(Exception):
    pass

class NotInstantiableError(Exception):
    pass

class AlreadyRegisteredError(Exception):
    pass

class MethodProxy(object):
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
        if self.hooks_registered:
            raise AlreadyRegisteredError(repr(self))

        for registration in self.registrations:
            hook = registration.hook
            hook.register(self, *registration.args, **registration.keywords)
            self.hooks_registered.append(hook)

    def unregister(self):
        if not self.hooks_registered:
            raise NotRegisteredError(repr(self))

        for hook in self.hooks_registered:
            hook.unregister(self)
        self.hooks_registered = []

    def add_bound_method(self, instance):
        bound_method = getattr(instance, self.name)
        instance_id = id(instance)
        if instance_id in self.instances_to_methods:
            raise AlreadyRegisteredError("%r (id: %r) to %r" % (instance, instance_id, self))
        self.instances_to_methods[instance_id] = bound_method
        self.bound_methods.append(bound_method)

    def remove_bound_method(self, instance):
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
        for bound_method in self.bound_methods:
            bound_method(*args, **keywords)

    @classmethod
    def _get_method_regs(selfcls, method):
        try:
            return method._crow2events_method_regs_
        except AttributeError:
            return []

    def __repr__(self):
        return "MethodProxy(%s.%s.%s)" % (self.clazz.__module__, self.clazz.__name__,
                                            self.name)

class ClassRegistration(object):
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
        for proxy in self.method_proxies:
            proxy.register()
        self.proxies_registered = True

    def unregister_proxies(self):
        for proxy in self.method_proxies:
            proxy.unregister()
        self.proxies_registered = False

    def __call__(self, *call_args, **call_keywords):
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
            self.free_instance(instance)
        if hasattr(instance, "delete"):
            log.msg("WARNING: about to obliterate instance %r's attribute delete"
                               " with %r!" % (instance, delete))
        instance.delete = delete
        return instance


    def free_instance(self, instance):
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
        calldict.update({"calling_hook": self})
        return (calldict,), {}

    def _fire_call_list(self, calllist, *args, **keywords):
        # todo: exception handling
        # todo: cancel handling (should it be separate?)
        for handler in calllist:
            #try:
            handler(*args, **keywords)
            #except:
            #    log.err()
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
        if not node._is_taggroup and not dep.startswith(":"):
            # relative/local
            depsplit = dep.split(".")
            namesplit = self._get_name(node.target).split(".")
            for up in (1, 2):
                relative_dep = ".".join(namesplit[:-up] + depsplit)
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
        if type(dep) == str:
            registration = self._lookup_strdep(node, dep)
        elif hasattr(dep, "_is_taggroup"):
            return dep
        else:
            handler = self.references[dep]
            registration = self.handler_references[handler]
        return registration

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
        before = self._tuplize_dependency(keywords.get("before", tuple()))
        after = self._tuplize_dependency(keywords.get("after", tuple()))
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
        @functools.wraps(func)
        def unregister_callback(*call_args, **call_keywords):
            try:
                return func(*call_args, **call_keywords)
            finally:
                self.unregister(unregister_callback)
        self.register(unregister_callback, *reg_args, **reg_keywords)
        return func

    def unregister(self, func):
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
            method_regs = []
            func._crow2events_method_regs_ = method_regs
        reg = MethodRegistration(self, args, keywords)
        method_regs.append(reg)
        return func

    def register_instantiation(self, clazz, *reg_args, **reg_keywords):
        self.register(ClassRegistration(self, clazz), *reg_args, **reg_keywords)

        return clazz

    @paramdecorator
    def instantiate(self, cls, *args, **keywords):
        return self.register_instantiation(cls, *args, **keywords)

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

# '''
