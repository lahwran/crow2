from twisted.internet.protocol import Protocol, ReconnectingClientFactory
from twisted.protocols.basic import LineOnlyReceiver

from crow2 import hook, log
from crow2.lib import config
from crow2.events.hook import Hook
from crow2.events.hooktree import InstanceHook, HookMultiplexer, CommandHook

example_connection = {
    "server": "irc.example.net",
    "nick": "example",
    "user": "example",
    "realname": "example",
    "channels": ["#changeme"]
}

hook.createsub("connection")
hook.connection.addhook("made", Hook())

class ProtocolMultiplexer(HookMultiplexer):
    def __init__(self):
        super(ProtocolMultiplexer, self).__init__(preparer=Hook(),
                hook_class=CommandHook, raise_on_noname=False, childarg="command")

    def _get_or_create_child(self, handler, name):
        if not name:
            return self.preparer
        else:
            return super(ProtocolMultiplexer, self)._get_or_create_child(handler, name)

    def unregister(self, handler):
        try:
            self.preparer.unregister(handler)
            registrations = 1
        except NotRegisteredError:
            registrations = 0

        super(ProtocolMultiplexer, self).unregister(handler, registrations)


class TwistedConnection(LineOnlyReceiver):
    disconnect = hook.connection.addhook("disconnect", InstanceHook())
    received = hook.connection.addhook("received", InstanceHook(hook_class=ProtocolMultiplexer))
    sent = hook.connection.addhook("sent", InstanceHook(hook_class=ProtocolMultiplexer))

    def __init__(self, server):
        self.server = server
        self.delimiter = server.delimiter
        self.context = {"conn": self, "server": server}

    def connectionMade(self):
        hook.connection.made.fire(self.context)

    def connectionLost(self, reason):
        self.disconnect.fire(self.context, reason=reason)

    def lineReceived(self, line):
        self.received.fire(self.context, line=line)

class ConnectionFactory(ReconnectingClientFactory):
    def __init__(self, server):
        self.server = server

    def buildProtocol(self, addr):
        log.msg("Connected to irc server %r" % addr)
        self.resetDelay()
        self.server._reactor_connection = TwistedConnection(self.server)
        return self.server._reactor_connection

class Server(object):
    def __init__(self, reactor, name, options):
        self.name = name
        self.address = options["server"]
        self.port = options.get("port", 6667)
        self.nick = options["nick"]
        self.user = options.get("user", self.nick)
        self.realname = options.get("realname", self.user)
        self.channels = options["channels"]
        self.delimiter = options.get("newline", "\r\n")

        self._reactor_connection = None
        self.reactor = reactor
        self.factory = ConnectionFactory(self)

    def connect(self):
        self.reactor.connectTCP(self.address, self.port, self.factory)

@hook.config.new
def defaultconfig(event):
    event.config.setdefault("connections", {
        "example": example_connection
    })

@hook.init(before="init")
def loadreactor(event):
    from twisted.internet import reactor
    event.reactor = reactor

class UnconfiguredError(Exception):
    pass

hook.init.tag("ircinit", after=":config")
@hook.init(tag="ircinit")
def init(event):
    import sys
    log.startLogging(sys.stdout, setStdout=False)

    for conn_name in event.config.connections:
        conn_options = event.config.connections[conn_name]
        if conn_name == "example" and conn_options == example_connection:
            raise UnconfiguredError("Please configure your irc bot before starting it "
                            "(ie, replace the example connection)")

        server = Server(event.reactor, conn_name, conn_options)
        server.connect()

@hook.mainloop
def mainloop(event):
    event.reactor.run()

