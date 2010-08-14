#!/usr/bin/env python

import os
import sys

import yaml
from werkzeug import script
from cherrypy import wsgiserver

from daemon import Daemon


def make_app(config_file):
    """create a websod instance - a WSGI application"""
    import websod

    # config
    assert config_file.endswith('.yaml')
    # add current folder to path for post-integration scripts
    sys.path.insert(0, os.path.dirname(os.path.abspath(config_file)))

    config = yaml.load(open(config_file))
    websod.setup_app(websod.app, config)
    return websod.app


def make_initdb(config='config.yaml'):
    def initdb(config=('c', config)):
        make_app(config).db.init_database()
    return initdb


def make_shell(init_func=None, config='config.yaml', banner=None,
               use_ipython=True):
    """Returns an action callback that spawns a new interactive
    python shell.

    :param init_func: an optional initialization function that is
                      called before the shell is started.  The return
                      value of this function is the initial namespace.
    :param banner: the banner that is displayed before the shell.  If
                   not specified a generic banner is used instead.
    :param use_ipython: if set to `True` ipython is used if available.
    """
    if banner is None:
        banner = 'Interactive Werkzeug Shell'
    if init_func is None:
        init_func = dict
    def action(config=('c', config), ipython=use_ipython):
        """Start a new interactive python session (used on development)"""
        namespace = init_func(config)
        if ipython:
            try:
                import IPython
            except ImportError:
                pass
            else:
                sh = IPython.Shell.IPShellEmbed(banner=banner)
                sh(global_ns={}, local_ns=namespace)
                return
        from code import interact
        interact(banner, local=namespace)
    return action

# make_shell helper
def app_namespace(config):
    from websod import models # add this to current namespace
    models # keep pyflakes quiet
    application = make_app(config)
    return locals()


# TODO organize it in a way that sodd installation does not require werkzeug.
def make_sodd(daemon='', config='config.yaml'):
    def sodd_action(daemon=('d', daemon), config=('c', config)):
        """run sodd """
        from sodd.main import run_ci
        full_config = os.path.abspath(config)
        base_path = os.path.dirname(full_config)
        config_dict = yaml.load(open(full_config))

        if daemon in ('start', 'stop'):
            log = os.path.abspath('sodd.log')
            pid = os.path.abspath('sodd.pid')
            d = Daemon(pid, stdout=log, stderr=log)
            def run():
                run_ci(base_path, config_dict)
            d.run = run
            # start/stop
            getattr(d, daemon)()
        elif daemon == '':
            run_ci(base_path, config_dict)
        else:
            print "Error use 'start'/'stop' for daemon mode, or None"
    return sodd_action


def make_cherryserver(daemon='', config='config.yaml',
                      hostname="localhost", port=9000,):
    def start_server(daemon=('d', daemon), config=('c', config),
                     hostname=('h', hostname), port=('p', port)):
        """Start websod using CherryPy (deployment)"""
        full_config = os.path.abspath(config)

        # FIXME log errors and access, see:
        # http://old.nabble.com/Logging-to-screen-with-a-WSGI-application...-td20784864.html
        server = wsgiserver.CherryPyWSGIServer((hostname, port),
                                               make_app(full_config))

        if daemon in ('start', 'stop'):
            log = os.path.abspath('websod.log')
            pid = os.path.abspath('websod.pid')
            d = Daemon(pid, stdout=log, stderr=log)
            def run():
                server.start()
            d.run = run
            # start/stop
            getattr(d, daemon)()
        else:
            print "Error use start/stop"
    return start_server



def make_flaskserver(config='config.yaml'):
    def run(config=('c', config)):
        flask_app = make_app(config)
        flask_app.run(debug=True)
    return run




if __name__ == "__main__":
    # initdb
    action_initdb = make_initdb()

    # dev shell
    action_shell = make_shell(app_namespace)

    # sodd
    action_sodd = make_sodd()

    # deployment websod
    action_cherryserver = make_cherryserver()

    # development websod
    action_runserver = make_flaskserver()

    script.run()
