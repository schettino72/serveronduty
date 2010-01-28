#!/usr/bin/env python

"""daemonize sodd & websod"""

import os
import sys
from getopt import gnu_getopt
from sodd.daemon import Daemon
from sodd import sodd
from manage import start_web_server

class SodDaemon(Daemon):
    def set_proj_file(self, proj_file):
        self.proj_file = proj_file

    def run(self):
        sodd.main(self.proj_file)

    def is_run(self):
        return os.path.exists(self.pidfile)

class WebserverDaemon(Daemon):
    def set_host(self, host):
        self.host = host

    def set_port(self, port):
        self.port = port

    def run(self):
        start_web_server(self.host, self.port)

    def is_run(self):
        return os.path.exists(self.pidfile)

base_dir = os.getcwd()
# since sodd/sodd.py uses relative path, we change the current directory
# to ./sodd/. But i think we need to fix that because IMO it's better to 
# use absolute path.
chdir_ = '%s/sodd/' % base_dir
sodd_pid_file = '%s/sodd.pid' % base_dir
webserver_pid_file = '%s/webserver.pid' % base_dir
# can set output despretor to '/dev/stdout' or '/dev/stderr' to debug
#stdout_ = '/dev/null'
#stderr_ = '/dev/null'
stdout_ = '/dev/stdout'
stderr_ = '/dev/stderr'
sod_d = SodDaemon(sodd_pid_file, dir_=chdir_, stdout=stdout_, stderr=stderr_)
webserver_d = WebserverDaemon(webserver_pid_file, dir_=base_dir,
                                        stdout=stdout_, stderr=stderr_)

def start_sodd(proj_file):
    """run the sodd as a daemon, proj_file could be 'doit.yaml' or
    'nbet.yaml'. maybe we need to move these files from sodd directory
    to to the root directory.
    """
    print 'starting the sodd...'
    sod_d.set_proj_file(proj_file)
    sod_d.start()
    print 'sodd started.'

def stop_sodd():
    print 'Stoping the sodd...'
    sod_d.stop()
    print 'sodd stopped.'

def start_web(host, port):
    print 'Starting the webserver'
    webserver_d.set_host(host)
    webserver_d.set_port(port)
    webserver_d.start()
    print 'webserver started'

def stop_web():
    print 'Stoping the webserver'
    webserver_d.stop()
    print 'Webserver stoped'

def status():
    if sod_d.is_run():
        print "Sodd IS WORKING"
    else:
        print "Sodd IS NOT WORKING"
    if webserver_d.is_run():
        print "Webserver IS WORKING"
    else:
        print "Webserver IS NOT WORKING"

def show_help():
    print """usage: sodd_ctl.py <action> [<options>]

actions:
  start <daemon>:
    start a server as a daemon

    start sodd                   start sodd
          --file <filename>      default file name is `project.yaml` 

    start webserver              start a webserver
          --port <port>          default port number is 9000
          --host <hostname>      default is `localhost`

    start all                    start sodd and webserver
          --file <filename>      default file name is `project.yaml` 
          --port <port>          default port number is 9000
          --host <hostname>      default is `localhost`

  stop <daemon>:
    stop the daemon

    stop sodd                    stop sodd
    stop webserver               stop the webserver
    stop all                     stop sodd and webserver

  status:
    check the status of daemons

options:
  --file <filename>:
    identify the yaml file we used in project when we start the sodd
    default file name is `project.yaml`
"""


def main():
    opts, args = gnu_getopt(sys.argv[1:], '',
                                         ['file=', 'port=', 'host='])
    # FIXME remove this default
    # default project file name is `project.yaml`
    proj_name = 'project.yaml'
    port = 9000
    host = 'localhost'
    for item in opts:
        if item[0] == '--file':
            proj_name = item[1]
        if item[0] == '--port':
            port = int(item[1])
        if item[0] == '--host':
            host = item[1]

    if len(args) == 0:
        show_help()
    elif args[0] == 'start':
        if args[1] == 'sodd':
            start_sodd(proj_name)
        elif args[1] == 'webserver':
            start_web(host, port)
        elif args[1] == 'all':
            # This is very bad, but can't find a better way
            pid = os.fork()
            if pid > 0:
                start_sodd(proj_name)
            else:
                start_web(host, port)
        else:
            show_help()
    elif args[0] == 'stop':
        if args[1] == 'sodd':
            stop_sodd()
        elif args[1] == 'webserver':
            stop_web()
        elif args[1] == 'all':
            stop_sodd()
            stop_web()
        else:
            show_help()
    elif args[0] == 'status':
        status()
    else:
        show_help()

if __name__ == '__main__':
    main()

