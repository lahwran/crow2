"""
Crow2 twisted plugin-based app system
"""
from crow2.events.hooktree import HookTree
from twisted.python import log # in case we change how we log

__all__ = ["hook", "log"]
hook = HookTree()
