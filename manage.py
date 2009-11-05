#!/usr/bin/env python

from werkzeug import script
from cherrypy import wsgiserver

def make_app():
    from websod.application import WebSod
    return WebSod('sqlite:///sod.db')

def make_shell():
    from websod import models, utils
    application = make_app()
    return locals()

def make_server(hostname="localhost", port=9000):
    def start_server(hostname=('h', hostname), port=('p', port)):
        """start a serveronduty server
        """
        server = wsgiserver.CherryPyWSGIServer((hostname, port), make_app())
        try:
            server.start()
        except KeyboardInterrupt:
            print '\nstopping...'
            server.stop()
    return start_server


action_start = make_server()
action_runserver = script.make_runserver(make_app, use_reloader=True,
                                         use_debugger=True)
action_shell = script.make_shell(make_shell)
action_initdb = lambda: make_app().init_database()

script.run()
