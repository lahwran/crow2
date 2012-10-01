from crow2.irc import main
from crow2 import hook, log

from crow2.events.handlerclass import handlerclass, instancehandler

import re

# TODO: rewrite back to using re_gen; re_gen needs work first
space = r"\ +"
prefix = """
    (?P<prefix>
        {servername} | {nick} (?:!{user})? (?:@{host})?
    )
"""

message = re.compile("""
    ^
    (?:
        :{prefix}{space}
    )?
    (?P<command>
        [a-zA-Z]+ | [0-9]{3}
    )
    (?P<params>
        {space}.+
    )
    $
""".format(prefix=prefix, space=space), flags=re.VERBOSE)

params = re.compile("""
    (?:
        [^:]
    )
""".format(), flags=re.VERBOSE)

@handlerclass(hook.connection.made)
class IRCProtocol(object):
    def __init__(self, event):
        pass

    @instancehandler.conn.disconnect
    def disconnected(self, event):
        self.delete()

    @instancehandler.conn.received.preparer
    def line_received(self, event):
        if not len(event.message):
            event.cancel()
            return
        
        event.command = "derp"

    @instancehandler.conn.received(name="derp")
    def derp_received(self, event):
        pass

@hook.connection.received.preparer
def irc_log(event):
    log.msg("irc message: %r" % event.line)
