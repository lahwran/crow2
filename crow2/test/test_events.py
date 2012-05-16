"""
Tests for things in crow2.events
"""
# pylint: disable = E1101
# pylint: disable = E0102
# pylint: disable = W0613
# pylint: disable = W0612
# pylint: disable = C0111
from crow2 import events
import pytest
import crow2.test.setup # pylint: disable = W0611




'''
def test_idea():
    class Arguments(tuple):
        def _add_dict(self, d):
            self.keywords = d
        def __getattr__(self, attr):
            try:
                return self.keywords[attr]
            except KeyError:
                raise AttributeError
    derp = Arguments((1, 2))
    derp._add_dict(dict(c=5, d=6))
    a, b = derp
    assert a == 1
    assert b == 2
    assert tuple(derp) == (1, 2)
    assert derp.c == 5
    assert derp.d == 6

def test_other_idea():
    class Arguments(tuple):
        def _add_dict(self, d):
            self.keywords = d
        def __getitem__(self, item):
            try:
                return super(Arguments, self).__getitem__(item)
            except TypeError:
                return self.keywords[item]
    derp = Arguments((1, 2))
    derp._add_dict(dict(c=5, d=6))
    a, b = derp
    assert a == 1
    assert b == 2
    assert tuple(derp) == (1, 2)
    assert derp["c"] == 5
    assert derp["d"] == 6
    assert derp[0] == 1
    assert derp[1] == 2

def test_somewhat_better_idea():


    derp = Arguments((1, 2), dict(c=5, d=6))
    a, b = derp
    assert a == 1
    assert b == 2
    assert tuple(derp) == (1, 2)
    assert derp.c == 5
    assert derp.d == 6
    assert derp["c"] == 5
    assert derp["d"] == 6
    assert derp[0] == 1
    assert derp[1] == 2
    with pytest.raises(KeyError):
        derp["e"]
    with pytest.raises(IndexError):
        derp[4]
    with pytest.raises(AttributeError):
        derp.f
'''
