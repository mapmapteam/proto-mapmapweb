#!/usr/bin/env python

from twisted.web import resource
from twisted.web import server
from twisted.internet import reactor

class Simple(resource.Resource):
    isLeaf = True
    def render_GET(self, request):
        return "<html>Hello, world!</html>"

class WebInterface(object):
    """
    Web UI
    """
    def __init__(self, port):
        self._site = server.Site(Simple())
        self._port = port
        reactor.listenTCP(self._port, self._site)

def run():
    web_ui = WebInterface(8080)
    reactor.run()

if __name__ == "__main__":
    run()

