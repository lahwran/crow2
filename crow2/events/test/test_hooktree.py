
from crow2.events.hooktree import HookTree, HookMultiplexer
from crow2.events.hook import Hook
from crow2.events.exceptions import AlreadyRegisteredError, NameResolutionError, NotRegisteredError
from crow2.test.util import Counter
import pytest



def test_command():
    hook = HookMultiplexer()
    counter = Counter()

    @hook
    def derp(event):
        counter.tick()

    assert counter.count == 0
    hook.fire(name="derp")
    assert counter.count == 1
    with pytest.raises(NameResolutionError):
        hook.fire(name="")
        
def test_preparer():
    hook = HookMultiplexer(preparer=Hook())
    counter1 = Counter()
    counter2 = Counter()
    counter_mapped = Counter()
    counter_preparer = Counter()

    @hook
    def derp(event):
        counter1.tick()

    @hook("herp")
    def herp(event):
        counter2.tick()

    mapping = {
            "dink": "herp",
            "donk": "derp"
    }

    @hook.preparer
    def prepare(event):
        if event.child_name in mapping:
            event.child_name = mapping[event.child_name]
            counter_mapped.tick()
        counter_preparer.tick()

    assert counter1.count == 0
    assert counter2.count == 0
    assert counter_preparer.count == 0
    assert counter_mapped.count == 0

    hook.fire(name="dink")

    assert counter1.count == 0
    assert counter2.count == 1
    assert counter_preparer.count == 1
    assert counter_mapped.count == 1

    hook.fire(name="donk")

    assert counter1.count == 1
    assert counter2.count == 1
    assert counter_preparer.count == 2
    assert counter_mapped.count == 2

    hook.fire(name="herp")
    
    assert counter1.count == 1
    assert counter2.count == 2
    assert counter_preparer.count == 3
    assert counter_mapped.count == 2

    hook.fire(name="derp")

    assert counter1.count == 2
    assert counter2.count == 2
    assert counter_preparer.count == 4
    assert counter_mapped.count == 2

def test_hooktree():
    counter = Counter()
    hook = HookTree(Hook)
    hook.createhook("test")

    @hook.test
    def afunc(event):
        counter.tick()
    hook.test.fire()

    @hook.instantiatehook("special")
    class SpecialHook(Hook):
        def derp(self):
            counter.tick()

    hook.special.derp()
    assert counter.count == 2
