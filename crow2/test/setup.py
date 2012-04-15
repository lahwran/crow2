from twisted.python import log
import sys

class Logger(object):
    """late-bound sys.stdout"""
    def write(self, msg):
        sys.stdout.write(msg)

    def flush(self):
        sys.stdout.flush()
        # sys.stdout will be changed by py.test later.
log.startLogging(Logger(), setStdout=0)
