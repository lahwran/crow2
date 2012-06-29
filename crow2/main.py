from crow2 import hook
from crow2 import plugin
from crow2 import util

class AlreadyRunningError(util.ExceptionWithMessage):
    "Main loop cannot be started from within mainloop"

class MainloopHook(object):
    def __init__(self):
        self.mainloop = None

    def fire(self, *contexts, **keywords):
        try:
            if not self.mainloop:
                return
        except AttributeError:
            raise AlreadyRunningError()

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
    def __init__(self, hook, core, plugins):
        self.hook = hook
        self.hook.createhook("init")
        self.hook.createhook("deinit")
        self.hook.createhook("stopmainloop")
        self.hook.createhook("mainloop", hook_class=MainloopHook)

        self.core_loader = plugin.Tracker(core)
        self.plugin_loaders = [plugin.Tracker(package) for package in plugins]

        self.load()

    def load(self):
        self.core_loader.load()
        for loader in self.plugin_loaders:
            loader.load()

    def run(self):
        self.hook._unlazy()
        event = self.hook.init.fire(main=self)
        self.hook.mainloop.fire(event, main=self)
        self.hook.deinit.fire(event, main=self)

    def quit(self, exitcode=0):
        self.hook.stopmainloop.fire(main=self, exitcode=exitcode)

def scriptmain(sysargs=None):
    if sysargs is None:
        import sys
        sysargs = sys.argv[1:]

    try:
        import argparse
    except ImportError as e:
        error = e.message + ("\n\nFailed to import argparse. Please install it with:\n"
                 "\n"
                 "    [sudo] pip install argparse\n"
                 "\n"
                 "(or, upgrade to python 2.7)")
        raise ImportError(error)

    parser = argparse.ArgumentParser()
    parser.add_argument("core", help="Core package-module of plugins to load")
    parser.add_argument("plugins", nargs="*",
            help="Plugin package-modules to load in addition to core-set "
                "(can be specified multiple times)")
    args = parser.parse_args(sysargs)

    main = Main(hook, args.core, args.plugins)
    main.run()
