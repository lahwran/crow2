from crow2.util import AttrDict, paramdecorator
from .exceptions import AlreadyRegisteredError, NotRegisteredError, NotInstantiableError
import inspect
import functools
from twisted.python import log

class HookMethodProxy(object):
    """
    Method proxy - multiplexes a single method to all bound methods that have been created by
    a ClassRegistration
    """
    def __init__(self, methodfunc):
        self.methodfunc = methodfunc
        self.registrations = []

        self.hooks_registered = []
        self.classes_registered = set()
        self.unbound_methods = []

        self.bound_methods = set()

    def addhook(self, hook, args, kwargs):
        self.registrations.append((hook, args, kwargs))
        if self.classes_registered:
            hook.register(self, *args, **kwargs)
            self.hooks_registered.append(hook)

    def register(self, clazz, name):
        """
        register this method proxy with all hooks that the method was attached to
        """
        if (clazz, name) in self.classes_registered:
            raise AlreadyRegisteredError("Already registered %r to handle method for class %r" % (self, clazz))
        self.unbound_methods.append(getattr(clazz, name))

        if not self.classes_registered:
            for registration in self.registrations:
                hook = registration[0]
                hook.register(self, *registration[1], **registration[2])
                self.hooks_registered.append(hook)
        self.classes_registered.add((clazz, name))

    def unregister(self, clazz, name):
        """
        unregister this method proxy from it's hooks
        """
        if (clazz, name) not in self.classes_registered:
            raise NotRegisteredError("%r is not registered to handle method for class %r" % (self, clazz))
        self.classes_registered.remove((clazz, name))
        self.unbound_methods.remove(getattr(clazz, name))

        if not self.classes_registered:
            for hook in self.hooks_registered:
                hook.unregister(self)
            self.hooks_registered = []

    def add_bound_method(self, bound_method, event):
        """
        register a bound method for an instance of the class this proxy's method belongs to
        """
        if bound_method in self.bound_methods:
            raise AlreadyRegisteredError("%r to %r" % (bound_method, self))
        self.bound_methods.add(bound_method)

    def remove_bound_method(self, bound_method):
        """
        remove a bound method belonging to the provided instance; instance must have a bound method registered with
        this proxy
        """
        try:
            self.bound_methods.remove(bound_method)
        except KeyError:
            raise NotRegisteredError("%r to %r" % (bound_method, self))

    def __call__(self, *args, **keywords): #TODO: we can probably replace this with just `event`
        """
        pass along a call to all bound methods
        """
        for bound_method in self.bound_methods:
            bound_method(*args, **keywords)

    @property
    def _proxy_for(self):
        return (self.methodfunc,) + tuple(self.unbound_methods)

    def __repr__(self):
        return "MethodProxy(%r)" % self.methodfunc

class InstanceHookReference(object):
    def __init__(self, names, simple_call, func, args, keywords):
        self.names = names
        self.simple_call = simple_call
        self.func = func
        self.args = args
        self.keywords = keywords

        self.method_hooks = {}

    def register(self, clazz, name):
        pass

    def unregister(self, clazz, name):
        pass

    def add_bound_method(self, bound_method, event):
        obj = event
        for name in self.names:
            obj = getattr(obj, name)
        print obj, bound_method

        if self.simple_call:
            obj(bound_method)
        else:
            obj(*self.args, **self.keywords)(bound_method)

        self.method_hooks[bound_method] = obj

    def remove_bound_method(self, bound_method):
        self.method_hooks[bound_method].unregister(bound_method)
        del self.method_hooks[bound_method]
        

class _InstanceHandler(object):
    def __init__(self, names=()):
        self.__names = names

    def __getattr__(self, name):
        return _InstanceHandler(self.__names + (name,))

    @paramdecorator(include_call_type=True)
    def __call__(self, func, *args, **keywords):
        """
        Mark a method for registration on instance init
        """
        is_simple_call = keywords.pop("paramdecorator_simple_call")
        try:
            instancehookregs = func._crow2_instancehookregs
        except AttributeError:
            func._crow2_instancehookregs = instancehookregs = []
        reg = InstanceHookReference(self.__names, is_simple_call, func, args, keywords)
        instancehookregs.append(reg)
        return func

instancehandler = _InstanceHandler()

@paramdecorator
def handlermethod(func, hook, *args, **keywords):
    try:
        hookmethodproxy = func._crow2_hookmethodproxy
    except AttributeError:
        func._crow2_hookmethodproxy = hookmethodproxy = HookMethodProxy(func)
    hookmethodproxy.addhook(hook, args, keywords)
    return func

def _get_method_regs(methodfunc):
    """
    helper to retrieve the method registrations from a provided method function
    """
    try:
        methodproxy = (methodfunc._crow2_hookmethodproxy,)
    except AttributeError:
        methodproxy = ()
    try:
        instancehooks = tuple(methodfunc._crow2_instancehookregs)
    except AttributeError:
        instancehooks = ()
    return methodproxy + instancehooks

class _HandlerClass(object):
    """
    Proxies a class such that when an instance is called, the created instance will be tracked and
    any @hook.method-ed methods will be registered
    """
    def __init__(self, clazz):
        self.clazz = clazz
        flattened = AttrDict()
        self.flattened = flattened
        assert clazz is not None
        resolved_mro = inspect.getmro(clazz)
        for parentclass in reversed(resolved_mro):
            flattened.update(parentclass.__dict__)

        self._proxy_for = (clazz,)

        init = flattened['__init__']
        if _get_method_regs(init):
            raise NotInstantiableError("%r: cannot register class %r for instantiation with listening __init__" % 
                                        (self, clazz))

        self.method_regs = set()
        self.registered = False
        for name, attribute in flattened.items():
            regs = _get_method_regs(attribute)
            if regs:
                for reg in regs:
                    self.method_regs.add((name, reg))

        self.instance_methods = {}
        self.instances = {}

    def register(self):
        """
        register all method proxies with their respective hooks
        """
        for name, reg in self.method_regs:
            reg.register(self.clazz, name)
        self.registered = True

    def unregister(self):
        """
        unregister all method proxies
        """
        for name, reg in self.method_regs:
            reg.unregister(self.clazz, name)
        self.registered = False

    def __call__(self, event):
        """
        Instantiate our class and begin tracking it

        1. instantiate the class
        2. add the instance to all of our method proxies
        3. shove a callback into the instance to allow it to ask us to delete it
        4. return the created instance
        """
        if not len(self.instances):
            if self.registered: # this is an invalid-internal-state case - pragma: no cover
                raise AlreadyRegisteredError("%r: about to register proxies, but proxies "
                            "are registered, and no previous instances known!" % self)
            self.register()

        instance = self.clazz(event)
        instance_id = id(instance)

        self.instances[instance_id] = instance
        methods = self.instance_methods[instance_id] = {}
        for name, reg in self.method_regs:
            method = getattr(instance, name)
            methods[name] = method
            reg.add_bound_method(method, event)

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

        methods = self.instance_methods[instance_id]
        for name, reg in self.method_regs:
            reg.remove_bound_method(methods[name])

        if not len(self.instances):
            if not self.registered: # this is an invalid-internal-state case - pragma: no cover
                raise NotRegisteredError("%r: about to unregister proxies, but proxies are already "
                                        "unregistered, and all instances already unregistered!" % self)
            self.unregister()

@paramdecorator
def handlerclass(clazz, hook, *args, **keywords):
    try:
        classreg = clazz._crow2_classreg
    except AttributeError:
        clazz._crow2_classreg = classreg = _HandlerClass(clazz)
    hook.register(classreg, *args, **keywords)
    return clazz
