#!/usr/bin/env python

import os

import yaml
from werkzeug import script
from cherrypy import wsgiserver

from daemon import Daemon


def make_app(config_file):
    """create a websod instance - a WSGI application"""
    from websod.application import WebSod
    from websod.utils import get_sa_db_uri

    # config
    assert config_file.endswith('.yaml')
    config = yaml.load(open(config_file))
    base_path = os.path.dirname(os.path.abspath(config_file))

    return WebSod(config, get_sa_db_uri(**config['db']))


def make_initdb(config='config.yaml'):
    def initdb(config=('c', config)):
        make_app(config).init_database()
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
    from websod import models, utils # add this to current namespace
    models, utils # keep pyflakes quiet
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
        base_path = os.path.dirname(full_config)

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


def make_runserver(app_factory, config='config.yaml',
                   hostname='localhost', port=5000,
                   use_reloader=False, use_debugger=False, use_evalex=True,
                   threaded=False, processes=1, static_files=None,
                   extra_files=None):
    """Returns an action callback that spawns a new development server.

    .. versionadded:: 0.5
       `static_files` and `extra_files` was added.

    :param app_factory: a function that returns a new WSGI application.
    :param hostname: the default hostname the server should listen on.
    :param port: the default port of the server.
    :param use_reloader: the default setting for the reloader.
    :param use_evalex: the default setting for the evalex flag of the debugger.
    :param threaded: the default threading setting.
    :param processes: the default number of processes to start.
    :param static_files: optionally a dict of static files.
    :param extra_files: optionally a list of extra files to track for reloading.
    """
    def action(config=('c', config), hostname=('h', hostname), port=('p', port),
               reloader=use_reloader, debugger=use_debugger,
               evalex=use_evalex, threaded=threaded, processes=processes):
        """Start a new development server."""
        from werkzeug.serving import run_simple
        app = app_factory(config)
        run_simple(hostname, port, app, reloader, debugger, evalex,
                   extra_files, 1, threaded, processes,
                   static_files=static_files)
    return action






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
    action_runserver = make_runserver(make_app, use_reloader=True,
                                      use_debugger=True)

    script.run()
