
class InvertedInt(int):
    def __nonzero__(self):
        return not int.__nonzero__(self)

class Counter(object):
    """
    a mutable counter to work around lack of nonlocal;
    used for testing if callbacks got called
    """
    def __init__(self):
        self.count = 0
        self.last_incremented = 0

    def tick(self):
        "Increment the counter by 1"
        self.count += 1

    def incremented(self, amount):
        delta = self.count - self.last_incremented
        result = InvertedInt(delta - amount) # opposite truth value - 0 is True, anything else is False
        self.last_incremented = self.count
        return result

