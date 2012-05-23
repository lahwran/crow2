
class Counter(object):
    """
    a mutable counter to work around lack of nonlocal;
    used for testing if callbacks got called
    """
    def __init__(self):
        self.count = 0
    def tick(self):
        "Increment the counter by 1"
        self.count += 1

