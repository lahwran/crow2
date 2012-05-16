import functools
from twisted.python import log
from crow2.util import paramdecorator

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

