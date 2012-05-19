import functools
from twisted.python import log
from twisted.internet.defer import Deferred
from crow2.util import paramdecorator, DecoratorPartial
from zope.interface import Interface, Attribute, implementer
from crow2.adapterutil import adapter_for
from crow2.events._base import IHook, IPartialHook

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

class IYieldedCallback(Interface):
    def __call__(target):
        """
        register a handler to be called once
        """

@adapter_for(Deferred, IYieldedCallback)
def adapt_deferred(deferred):
    return deferred.addCallback

@adapter_for(IHook, IYieldedCallback)
def adapt_hook(hook):
    return hook.once

@adapter_for(IPartialHook, IYieldedCallback)
def adapt_partial_hook(partial):
    partial = partial.copy()
    hook = partial.args[0].__class__
    partial.func = hook.register_once.im_func
    return partial

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
            hook = IYieldedCallback(yielded)
            hook(callback)
    send = next

    def make_callback(self):
        "produce a callback which can only be called once"
        next_call_position = self.call_position + 1
        @functools.wraps(self.factory)
        def callback(event):
            "callback which will check that it's called at the right time"
            self.call_position += 1
            assert self.call_position == next_call_position

            self.next(event)
        callback.__name__ += "/%d" % next_call_position # pylint: disable=E1101
        return callback
