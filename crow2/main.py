from crow2 import hook
from crow2 import plugin
from crow2.events import ClassregMixin

class MainloopHook(ClassregMixin):
    def __init__(self):
        self.mainloop = None

    def fire(self, *contexts, **keywords):
        from crow2.util import AttrDict
        event = AttrDict()
        for context in contexts + (keywords,):
            event.update(context)
        mainloop = self.mainloop # if a plugin tries to start the mainloop again, it should fail
        del self.mainloop
        mainloop(event)
        self.mainloop = mainloop

    def register(self, target):
        if self.mainloop:
            from crow2.events.exceptions import AlreadyRegisteredError
            raise AlreadyRegisteredError("Only one mainloop can be registered")

        self.mainloop = target
    __call__ = register

class Main(object):
    def __init__(self, core, plugins):
        hook.createhook("init")
        hook.createhook("deinit")
        hook.createhook("stopmainloop")
        hook.createhook("mainloop", hook_class=MainloopHook)

        self.core_loader = plugin.PackageLoader(core)
        self.plugin_loaders = [plugin.PackageLoader(package) for package in plugins]

        self.load()

    def load(self):
        self.core_loader.load()
        for loader in self.plugin_loaders:
            loader.load()

    def run(self):
        hook.init.fire(main=self)
        hook.mainloop.fire(main=self)
        hook.deinit.fire(main=self)

    def quit(self, exitcode=0):
        hook.stopmainloop.fire(main=self, exitcode=exitcode)

def scriptmain(sysargs=None):
    if not sysargs:
        import sys
        sysargs = sys.argv[1:]

    try:
        import argparse
    except ImportError:
        print "Failed to import argparse. Please install it with:"
        print
        print "    [sudo] pip install argparse"
        print
        print "(or, upgrade to python 2.7)"

    parser = argparse.ArgumentParser()
    parser.add_argument("core", help="Core package-module of plugins to load")
    parser.add_argument("plugins", nargs="*",
            help="Plugin package-modules to load in addition to core-set "
                "(can be specified multiple times)")
    args = parser.parse_args(sysargs)

    main = Main(args.core, args.plugins)
    main.run()
