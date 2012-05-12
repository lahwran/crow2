"""
Utilities for global test state initialization; import to activate
"""

from twisted.python import log
import sys

class Logger(object):
    """
    Utility to allow use of twisted's logging in py.test
    """
    def write(self, msg):
        "write a message to stdout"
        sys.stdout.write(msg)

    def flush(self):
        "flush stdout"
        sys.stdout.flush()
        # sys.stdout will be changed by py.test later.
log.startLogging(Logger(), setStdout=0)
