from twisted.internet.defer import Deferred

from crow2.events.hook import Hook
from crow2.events.yielding import yielding
from crow2.util import AttrDict

def test_simple():
    """
    "Simple" test of yielding
    """
    hook1 = Hook()
    hook2 = Hook()

    @hook1
    @yielding
    def handler(event):
        "yielding handler"
        while "derp" in event:
            event = yield event.derp
        event.was_called = True

    assert handler #shut up, pylint

    # when we pass nothing in, it doesn't see "derp" in event and so just returns
    assert "was_called" in hook1.fire()

    # nothing is registered to hook2 at the moment
    assert not "was_called" in hook2.fire()

    # when we pass hook2 into hook1's handler, it yields it, and so hook1's event never gets modified
    assert not "was_called" in hook1.fire(derp=hook2)
    # now, since hook2 was yielded from hook1's handler, when we fire hook2
    # with no arguments it's event gets modified
    assert "was_called" in hook2.fire()

    # but if we call hook2 again, nothing happens, since the yield handler finished
    assert not "was_called" in hook2.fire()

    # now we pass back and forth just to be sure it works
    assert not "was_called" in hook1.fire(derp=hook2)
    assert not "was_called" in hook2.fire(derp=hook1)
    assert not "was_called" in hook1.fire(derp=hook2)
    # aaand, call without arguments. are you still there, handler?
    assert "was_called" in hook2.fire()
    # if we got here, yep!

def test_partial_adaptation():
    hook1 = Hook()
    hook2 = Hook()

    @hook2
    def first(event):
        event.before_called = True

    @hook2
    def third(event):
        assert event.handler_called
        event.after_called = True

    @hook1
    @yielding
    def handler(event):
        event.handler_called = True

        event = yield hook2(after=first, before=third)

        assert event.before_called
        event.handler_called = True
        
    first_event = hook1.fire()
    assert first_event.handler_called

    second_event = hook2.fire()
    assert second_event.after_called

def test_deferred_adaptation():
    hook1 = Hook()

    @hook1
    @yielding
    def handler(event):
        event.handler_called = True
        deferred_result = yield event.deferred
        deferred_result.handler_called = True

    event = hook1.fire(deferred=Deferred())

    newevent = AttrDict()
    event.deferred.callback(newevent)
    assert newevent.handler_called
