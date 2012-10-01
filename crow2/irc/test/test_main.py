import sys

import pytest

from crow2 import hook
from crow2.util import AttrDict
from crow2.events.hook import Hook
from crow2.test.util import Counter
from ...irc import main

def test_mainloop():
    counter = Counter()

    def run():
        counter.tick()
    reactor = AttrDict(run=run)
    event = AttrDict(reactor=reactor)

    main.mainloop(event)

    assert counter.incremented(1)

def test_init(monkeypatch):
    startLogging_counter = Counter()

    def startLogging(outfile, setStdout=True):
        assert setStdout == False
        assert outfile is sys.stdout
        startLogging_counter.tick()

    logstub = AttrDict(startLogging=startLogging)
    fakeservers = {}
    class FakeServer(object):
        def __init__(self, reactor, name, options):
            self.reactor = reactor
            self.name = name
            self.options = options
            self.connected = False
            fakeservers[name] = self

        def connect(self):
            self.connected = True

    monkeypatch.setattr(main, "log", logstub)
    monkeypatch.setattr(main, "Server", FakeServer)

    reactor_sentinel = object()

    connections = {
        "test_1": object(),
        "test_2": object()
    }
    config = AttrDict(connections=connections)
    event = AttrDict(config=config, reactor=reactor_sentinel)

    main.init(event)

    assert startLogging_counter.incremented(1)
    assert len(fakeservers) == len(connections)
    assert all(fakeserver.reactor is reactor_sentinel for fakeserver in fakeservers.values())
    assert all(fakeserver.connected for fakeserver in fakeservers.values())

    assert fakeservers["test_1"].options is connections["test_1"]
    assert fakeservers["test_2"].options is connections["test_2"]

def test_init_unconfigured(monkeypatch):
    monkeypatch.setattr(main, "log", AttrDict(startLogging=lambda out, setStdout: None))

    class FakeServer(object):
        def __init__(self, reactor, name, options):
            should_never_run()

        def connect(self):
            should_never_run()

    monkeypatch.setattr(main, "Server", FakeServer)

    reactor_sentinel = object()

    event = AttrDict(config=AttrDict())
    main.defaultconfig(event)

    with pytest.raises(main.UnconfiguredError):
        main.init(event)

def test_defaultconfig(monkeypatch):
    event = AttrDict(config=AttrDict())

    assert event == {"config": {}}

    main.defaultconfig(event)

    assert event == {
        "config": {
            "connections": {
                "example": {
                    "server": "irc.example.net",
                    "nick": "example",
                    "user": "example",
                    "realname": "example",
                    "channels": [
                        "#changeme"
                    ]
                }
            }
        }
    }

def test_loadreactor(monkeypatch):
    from twisted.internet import reactor

    event = AttrDict()
    main.loadreactor(event)
    assert event == {"reactor": reactor}

def test_server_defaults(monkeypatch):

    options = AttrDict({
        "server": object(),
        "nick": object(),
        "channels": object()
    })

    reactor_sentinel = object()
    monkeypatch.setattr(main, "ConnectionFactory", lambda server: None)

    server = main.Server(reactor_sentinel, "connection_name", options)
    assert server.name == "connection_name"
    assert server.port == 6667

    assert server.address is options.server
    assert server.nick is options.nick
    assert server.channels is options.channels

    assert server.user is options.nick
    assert server.realname is options.nick
    assert server.delimiter == "\r\n"

    assert server.reactor is reactor_sentinel

def test_server_connect(monkeypatch):
    connections = []
    def fakeconnecttcp(address, port, factory):
        connections.append((address, port, factory))
    reactor = AttrDict(connectTCP=fakeconnecttcp)

    options = AttrDict({
        "server": object(),
        "port": object(),
        "nick": object(),
        "user": object(),
        "realname": object(),
        "channels": object(),
        "newline": object()
    })

    fakeconnectionfactories = []
    class FakeConnectionFactory(object):
        def __init__(self, serverobj):
            self.serverobj = serverobj
            fakeconnectionfactories.append(self)
    monkeypatch.setattr(main, "ConnectionFactory", FakeConnectionFactory)

    server = main.Server(reactor, "connection_name", options)
    assert server.address is options.server
    assert server.port is options.port
    assert server.nick is options.nick
    assert server.user is options.user
    assert server.realname is options.realname
    assert server.channels is options.channels
    assert server.delimiter is options.newline

    assert server.factory.serverobj is server # yay reference loop!
    assert not len(connections)

    server.connect()

    assert connections == [(options.server, options.port, fakeconnectionfactories[0])]

def test_protocol(monkeypatch):
    conn_hooks = AttrDict()
    monkeypatch.setattr(hook, "connection", conn_hooks)

    delimiter_sentinel = object()
    server = AttrDict(delimiter=delimiter_sentinel)
    factory = main.ConnectionFactory(server)
    assert factory.server is server

    protocol = factory.buildProtocol("irc.example.net")
    assert server._reactor_connection is protocol
    assert protocol.server is server
    assert protocol.delimiter is server.delimiter

    conn_hooks.made = Hook()
    result = AttrDict()
    updated = Counter()

    @conn_hooks.made
    def onmade(event):
        result.update(event)
        updated.tick()

    protocol.connectionMade()
    assert updated.incremented(1)

    # goes out of its way to not assert that the connection
    # object is actually what is passed into the event call
    @result.conn.received
    def received(event):
        assert event.line == "incoming line"
        event.received = True
        event.command = "command"

    commands = Counter()
    @result.conn.received("command")
    def received_command(event):
        assert event.received == True
        commands.tick()

    protocol.lineReceived("incoming line")
    assert commands.incremented(1)

    disconnect_count = Counter()
    reason_sentinel = object()
    @result.conn.disconnect
    def disconnected(event):
        assert event.reason is reason_sentinel
        disconnect_count.tick()

    protocol.connectionLost(reason_sentinel)
    assert disconnect_count.incremented(1)
