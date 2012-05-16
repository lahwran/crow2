"""
Message-passing "event" system
"""

from ._base import BaseHook
from ._classreg import ClassregHookMixin
from ._yielding import yielding

class Hook(BaseHook, ClassregHookMixin):
    pass
