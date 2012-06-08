from crow2.util import AttrDict, paramdecorator
from .exceptions import AlreadyRegisteredError, NotRegisteredError, NotInstantiableError
import inspect
import functools
from twisted.python import log


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

class HandlerClass(object):
    """
    Proxies a class such that when an instance is __call__ed, the created instance will be tracked and
    any @hook.method-ed methods will be registered
    """
    def __init__(self, clazz, hook=None):
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


class ClassregMixin(object):
    def register_instantiation(self, clazz, *reg_args, **reg_keywords):
        """
        Register a class for instantiation; registers the provided class through a ClassRegistration proxy
        """
        self.register(HandlerClass(clazz, self), *reg_args, **reg_keywords)

        return clazz

    @paramdecorator
    def instantiate(self, cls, *args, **keywords):
        """
        decorator version of register_instantiation
        """
        return self.register_instantiation(cls, *args, **keywords)

