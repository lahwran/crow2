from crow2 import events
class Counter(object):
    "a mutable counter"
    def __init__(self):
        self.count = 0
    def tick(self):
        self.count += 1

class TestHook(object):

    def test_simple():
        