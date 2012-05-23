"""
Plugin loading/unloading utilities
"""

import imp
import os
import sys

from twisted.python.reflect import namedModule

class AlreadyLoadedError(Exception): #TODO: these exceptions are duplicated in crow2.events
    "Trying to load when already loaded"

class NotLoadedError(Exception):
    "Trying to unload when not loaded"


class PackageLoader(object):
    """
    manages a plugin package - loads submodules as packages
    """
    def __init__(self, package, name=None):
        self.package = package
        self.loaded = False
        self.plugins = []
        self.name = name

    def load(self):
        """
        Load all modules in the package that this packageloader is in charge of
        """
        if self.loaded:
            raise AlreadyLoadedError(repr(self))
        self.plugins = []

        sys.dont_write_bytecode, olddwbc = True, sys.dont_write_bytecode
        try:
            try:
                names = listpackage(self.package)
            except ImportError:
                print "did you forget to add an __init__.py?"
                raise

            for name in names:
                plugin = namedModule(self.package + "." + name)
                self.plugins.append(plugin)
            self.loaded = True
        finally:
            sys.dont_write_bytecode = olddwbc
        # that was easy

    def unload(self):
        """
        unload all modules we have loaded
        """
        if not self.loaded:
            raise NotLoadedError(repr(self))
        for name in dict(sys.modules):
            if name.startswith(self.package+".") or name == self.package:
                del sys.modules[name]
        self.plugins = []
        self.loaded = False

        #unload from sys.modules, empty out our bowels

    def __repr__(self):
        return "<PackageLoader(%r)>" % self.package

    def __str__(self):
        return "Package %r: %s" % (self.package, self.name)

class ModuleLoader(object):
    "TODO: loads an individual module"
    def __init__(self, filename):
        pass

suffixes = set([info[0] for info in imp.get_suffixes()])
def getmodulename(parent, filename):
    """
    Get the name of a module based on it's filename
    """
    for suffix in suffixes:
        if filename.endswith(suffix):
            return filename[:-len(suffix)] # remove ending
    else:
        fullpath = os.path.join(parent, filename)
        if os.path.isdir(fullpath):
            for suffix in suffixes:
                if os.path.exists(os.path.join(fullpath, "__init__"+suffix)):
                    return filename

def listpackage(name):
    """
    List the children of a package
    """
    parent = namedModule(name)
    results = set()
    for package_path in parent.__path__:
        files = os.listdir(package_path)

        for filename in files:
            modulename = getmodulename(package_path, filename)
            if not modulename or modulename == "__init__":
                continue
            results.add(modulename)

    return results
