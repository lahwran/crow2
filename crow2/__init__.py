"""
Crow2 twisted plugin-based app system
"""
from crow2.events import HookTree

__all__ = ["hook"]
hook = HookTree()
