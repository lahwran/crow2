import weakref

from crow2.util import paramdecorator
from .hook import Hook, IDecoratorHook, DecoratorMixin
from .exceptions import AlreadyRegisteredError, NameResolutionError, NotRegisteredError
from zope.interface import implementer

class HookTree(object): #TODO: make this do stuff
    """
    Contains hooks or hookcategories. children can be accessed as attributes.
    """
    def __init__(self, default_hook_class=Hook, name=None):
        self._children = {}
        self._default_hook_class = default_hook_class
        self._name = name

    def __getattr__(self, attr):
        try:
            return self._children[attr]
        except KeyError:
            raise AttributeError

    @paramdecorator(argname="hook_class")
    def instantiatehook(self, name, hook_class, *args, **keywords):
        self.createhook(name, hook_class=hook_class, *args, **keywords)
        return hook_class

    def createhook(self, name, *args, **keywords):
        if name in self._children:
            raise AlreadyRegisteredError("Hook name %r already registered to me (%r)" % (name, self))

        hook_class = keywords.get("hook_class", self._default_hook_class)
        if "hook_class" in keywords:
            del keywords["hook_class"]

        instance = hook_class(*args, **keywords)
        self._children[name] = instance
        
        sentinel = object()
        instance_name = getattr(instance, "_name", sentinel)
        if instance_name is not sentinel:
            instance._name = "%s.%s" % (self._name, name)

        return instance

    def createsub(self, name, *args, **keywords):
        return self.createhook(name, hook_class=type(self), *args, **keywords)

    def addhook(self, name, instance):
        self._children[name] = instance
        return instance

    def __repr__(self):
        return "<HookTree %s>" % self._name

class ChildHook(Hook):
    def __init__(self, parent, name):
        super(ChildHook, self).__init__()
        self._parent = parent
        self._name = name

    def _attempt_freeing(self):
        if not len(self.registration_groups):
            self._parent._free_child(self)

    def unregister(self, target):
        super(ChildHook, self).unregister(target)
        self._attempt_freeing()

    def __repr__(self):
        parentname = self._parent._name
        if parentname is None:
            parentname = repr(self._parent)
        return "<%s %s[%r]>" % (type(self).__name__, parentname, self._name)

class CommandHook(ChildHook):
    main_tag = "main"
    def register(self, func, before=(), after=(), tag=None):
        if not before and not after and not tag:
            tag = self.main_tag

        if tag == self.main_tag and len(self.tags[tag].targets):
            raise AlreadyRegisteredError("The main handler for this command is already registered")

        keywords = {}
        if before:
            keywords["before"] = before
        if after:
            keywords["after"] = after
        if tag:
            keywords["tag"] = tag

        return super(CommandHook, self).register(func, **keywords)


@implementer(IDecoratorHook)
class HookMultiplexer(DecoratorMixin):
    def __init__(self, name=None, preparer=None, hook_class=ChildHook,
            childarg="name", raise_on_missing=True, raise_on_noname=True,
            missing=None):
        self._children = {}
        self._hook_class = hook_class
        self._name = name

        self.preparer = preparer
        self.missing = missing
        self.childarg = childarg
        self.raise_on_missing = raise_on_missing
        self.raise_on_noname = raise_on_noname

    def fire(self, *contexts, **keywords):
        name = None
        if self.childarg in keywords:
            name = keywords[self.childarg]
        elif self.raise_on_noname:
            raise TypeError("Required keywordarg %r (or 'name') not found" % self.childarg)

        keywords["multiplexer"] = self
        preparer_event = None
        if self.preparer:
            preparer_event = self.preparer.fire(*contexts, **keywords)
            if getattr(preparer_event, "cancelled", False):
                return preparer_event

            contexts = ()
            keywords = preparer_event
            name = preparer_event[self.childarg]

        try:
            command = self._children[name]
        except KeyError:
            if self.missing:
                keywords["name"] = name
                keywords[self.childarg] = name
                return self.missing.fire(*contexts, **keywords)
            elif self.raise_on_missing:
                raise NameResolutionError("No such child: %r" % name)
            else:
                return preparer_event

        return command.fire(*contexts, **keywords)

    def name_missing(self, handler, name):
        return handler.__name__

    def _get_or_create_child(self, handler, name):
        if not name:
            name = self.name_missing(handler, name)
        try:
            child = self._children[name]
        except KeyError:
            child = self._hook_class(parent=self, name=name)
            self._children[name] = child
        return child

    def _free_child(self, child):
        del self._children[child._name]

    def register(self, handler, name=None, **keywords):
        child = self._get_or_create_child(handler, name)
        return child.register(handler, **keywords)

    def register_once(self, handler, name=None, **keywords):
        child = self._get_or_create_child(handler, name)
        return child.register_once(handler, **keywords)

    def unregister(self, handler):
        registrations = 0
        for child in self._children.values():
            try:
                child.unregister(handler)
                registrations += 1
            except NotRegisteredError:
                pass
        if not registrations:
            raise NotRegisteredError("%r: no sub-hooks unregistered %r" % (self, handler))

    def __repr__(self):
        if self._name is None:
            return object.__repr__(self)
        return "<%s %s>" % (type(self).__name__, self._name)

@implementer(IDecoratorHook)
class _InstanceHookProxy(DecoratorMixin):
    def __init__(self, hook, instance_weakref, parent):
        self.hook = hook
        self.instance_weakref = instance_weakref
        self.parent = parent

    def fire(self, *args, **kwargs):
        kwargs["_instance"] = self.instance_weakref()
        return self.parent.fire(*args, **kwargs)

    def register(self, handler, **keywords):
        return self.hook.register(handler, **keywords)

    def register_once(self, handler, **keywords):
        return self.hook.register_once(handler, **keywords)

    def unregister(self, handler):
        return self.hook.unregister(handler)

    def __getattr__(self, name):
        return getattr(self.hook, name)


class InstanceHook(HookMultiplexer):
    def __init__(self, name=None, preparer_class=Hook, hook_class=Hook):
        super(InstanceHook, self).__init__(name=name,
                preparer=preparer_class(), hook_class=hook_class,
                childarg="_instance", raise_on_missing=True)
        self.instances = {}
        self._children = weakref.WeakKeyDictionary()
        self._child_proxies = weakref.WeakKeyDictionary()
    
    def __get__(self, instance, owner):
        if instance is None:
            return self

        try:
            return self._child_proxies[instance]
        except KeyError:
            self._children[instance] = self._hook_class()
            proxy = _InstanceHookProxy(self._children[instance], weakref.ref(instance), self)
            self._child_proxies[instance] = proxy
            return proxy
    
    def register(self, handler, **keywords):
        return self.preparer.register(handler, **keywords)
    
    def register_once(self, handler, **keywords):
        return self.preparer.register_once(handler, **keywords)
    
    def unregister(self, handler):
        return self.preparer.unregister(handler)
