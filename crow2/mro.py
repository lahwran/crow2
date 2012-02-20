"""
PEP8-refactored version of mro.py from
http://www.python.org/getit/releases/2.3/mro/#the-end

C3 algorithm by Samuele Pedroni (with readability enhanced by Michele Simionato).

@author: Michele Simionato
@author: Samuele Pedroni
@license: unknown, assumed public domain
"""

def merge(seqs):
    result = []
    while True:
        remaining = [sequence for sequence in seqs if sequence]
        if not remaining:
            return result
        for sequence in remaining: # find merge candidates among seq heads
            candidate = sequence[0]
            not_head = [s for s in remaining if candidate in s[1:]]
            if not_head:
                candidate = None # reject candidate
            else:
                break
        if not candidate:
            raise Exception("Inconsistent hierarchy")
        result.append(candidate)
        for sequence in remaining: # remove candidate
            if sequence[0] == candidate:
                del sequence[0]

def mro(cls):
    "Compute the class precedence list (mro) according to C3"
    return merge([[cls]]
                 + map(mro,cls.__bases__)
                 + [list(cls.__bases__)])