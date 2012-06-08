"""
Plugin loading/unloading utilities
"""

import imp
import os
import sys

from twisted.python.reflect import namedAny, namedModule

class AlreadyLoadedError(Exception): #TODO: these exceptions are duplicated in crow2.events
    "Trying to load when already loaded"

class NotLoadedError(Exception):
    "Trying to unload when not loaded"

class LoadError(Exception):
    "Failed to load for some reason"

class LoadRedirectError(LoadError):
    "Load failed because the modules redirected unresolvably"

# TODO: while not tired, verify this code and then remove excessive comments
# TODO: this needs a sprinkle of zen
def load(modulename, is_pluginset=True, filter_children=None, seen=None):
    """
    Load a module as whatever it looks like. Heavily commented due to being tired-code.
    """
    if seen is None:
        seen = set()

    found = set() # found is separate from seen because found is the actual result; seen is just tracking so we don't loop infinitely

    old_dont_write_bytecode = sys.dont_write_bytecode # if someone else messed with dont_write_bytecode (such as this function when recursing) store it so it can be restored
    sys.dont_write_bytecode = True # this is for reloading reasons - allowing python to write bytecode results in nastyness when reloading (though maybe it's pointless because reloading is so nasty anyway)
    try:
        current_module_name = modulename # copy the reference so that we don't lose sight of what we're loading as we resove references
        while current_module_name: # while we still have a reference to resolve
            if current_module_name in seen: # this needs to be inside the while loop so that the reference resolution gets checked
                raise LoadRedirectError("Going in loop")  # if the module we're being asked to load has already been loaded by this recursion, then we're going in a loop

            try:
                module = namedModule(current_module_name)
            except ImportError as e:
                # TODO: need to ensure this maintains context - it will eat any errors from bad code in plugins if it doesn't!
                raise LoadError("Failed to load %r (%r): %r" % (modulename, current_module_name, e.message))

            seen.add(current_module_name) # immediately mark the name as seen

            # save the name we ended up on so we can use it to find children
            # (this is overwritten each run of the loop, so it will only stick on the last run)
            final_module_name = current_module_name 
            try:
                current_module_name = module.crow2_module # try to grab a next name
            except AttributeError:
                current_module_name = None # no name? exit the loop

        found.add(module) # we found a module, so add it to the results

        load_children = getattr(module, "crow2_load_children_override", is_pluginset)
        if not load_children:
            return found

        loadable = getattr(module, "crow2_pluginset", False)
        if load_children and not loadable:
            raise LoadError("tried to load non-loadable module %r" % final_module_name)

        # if the module has an override for the child filtering, use that
        children = getattr(module, "crow2_children", filter_children)

        if not children: # loadchildren's True but no children were specified, autodetect them
            try:
                module_path = module.__path__ # try to get the path,
            except AttributeError:
                return found                  # but if it's not there then there are no children to be had, so just return what was found so far
            children = listpackage(module_path) # get the names from the path

        for child_name in children:
            # recurse to load the child - this is a big part of why we track seen; if the tree gets too complex, there could be whacky collisions. Errors should never pass silently!
            child_set = load(final_module_name + "." + child_name, False, None, seen)
            found.update(child_set) # okay, we have the child loaded, along with any children it may have explicitly specified for itself. add its results to our own (this could be a list currently because seen ensures uniqueness)

        return found # and lastly, we have done all we know how to to load this silly module. finish off by returning our handiwork
    finally:
        sys.dont_write_bytecode = old_dont_write_bytecode 

class Tracker(object):
    """
    manages a plugin package - loads submodules as packages
    """
    def __init__(self, modulename, description="plugins"):
        self.modulename = modulename
        self.loaded = False
        self.plugins = set()
        self.description = description

    def load(self):
        """
        Load all modules in the package that this packageloader is in charge of
        """
        if self.loaded:
            raise AlreadyLoadedError(repr(self))
        self.plugins = load(self.modulename)
        self.loaded = True

    '''
    def unload(self):
        """
        unload all modules we have loaded
        """
        #unload from sys.modules, empty out our bowels
        if not self.loaded:
            raise NotLoadedError(repr(self))
        for name in dict(sys.modules):
            if name.startswith(self.package+".") or name == self.package:
                del sys.modules[name]
        self.plugins = []
        self.loaded = False

    '''

    def __repr__(self):
        return "<plugin.Tracker(%r)>" % self.modulename

    def __str__(self):
        return "Plugin Tracker %r: %s" % (self.description, self.modulename)

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

def listpackage(path):
    """
    List the children of a package based on its __path__
    """
    results = set()
    for package_path in path:
        files = os.listdir(package_path)

        for filename in files:
            modulename = getmodulename(package_path, filename)
            if not modulename or modulename == "__init__":
                continue
            results.add(modulename)

    return results
