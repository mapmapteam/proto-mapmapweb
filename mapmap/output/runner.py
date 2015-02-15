#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MapMap output.
"""
from twisted.internet import gtk2reactor
gtk2reactor.install()

from twisted.internet import reactor
from optparse import OptionParser
from mapmap import __version__
import sys
from txosc import dispatch
from txosc import async
from twisted.internet.error import CannotListenError
from twisted.internet import task

DESCRIPTION = "MapMap video output"
DEFAULT_OSC_RECV_PORT = 9001

    
class App(object):
    """
    Application that shows a MapMap video output.
    """
    def __init__(self, verbose=False, osc_receive_port=DEFAULT_OSC_RECV_PORT):

        # OSC INPUT
        self._osc_recv_port = osc_receive_port
        if self._osc_recv_port is None:
            self._osc_recv_port = DEFAULT_OSC_RECV_PORT

        self._osc_receiver = dispatch.Receiver()
        try:
            self._osc_receive_server = reactor.listenUDP(self._osc_recv_port, async.DatagramServerProtocol(self._osc_receiver))
        except CannotListenError, e:
            print("Another instance of this application is already running!")
            print(e)
            sys.exit(1)

        if self._verbose:
            print("Listening on osc.udp://localhost:%s" % (self._osc_recv_port))
        self._osc_receiver.addCallback("/pattern", self._pattern_cb)

        if VERY_VERBOSE:
            if self._verbose:
                print("%s" % (self.__dict__))

        self._print_looping_call = task.LoopingCall(self._looping_cb)
        self._print_looping_call.start(1.0)

    def _looping_cb(self):
        pass

    def _pattern_cb(self, message, address):
        if message.getTypeTags() != "i":
            print("Wrong type tags: %s" % (message))
            return
        value = message.getValues()[0]
        if self._verbose:
            print("Pattern: %s" % (value))
        # TODO: change pattern

    def __del__(self):
        pass


def run():
    # command line parsing
    parser = OptionParser(usage="%prog", version=str(__version__), description=DESCRIPTION)
    parser.add_option("-p", "--osc-receive-port", type="int", help="OSC port to listen to for sensors")
    parser.add_option("-v", "--verbose", action="store_true", help="Enables a verbose logging output with info level messages.")
    (options, args) = parser.parse_args()

    app = App(
        verbose=options.verbose,
        osc_receive_port=options.osc_receive_port)
    print("Running mapmap-output")

    try:
        reactor.run()
    except KeyboardInterrupt:
        print("Bye")

