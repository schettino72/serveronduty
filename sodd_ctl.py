#!/usr/bin/env python
import os
import sys
from getopt import gnu_getopt
from sodd.daemon import Daemon
from sodd import sodd

class SoddDaemon(Daemon):
    def set_proj_file(self, proj_file):
        self.proj_file = proj_file

    def run(self):
        sodd.main(self.proj_file)

    def is_run(self):
        return os.path.exists(self.pidfile)

base_dir = os.getcwd()
# since sodd/sodd.py uses relative path, we change the current directory
# to ./sodd/. But i think we need to fix that because IMO it's better to 
# use absolute path.
chdir_ = '%s/sodd/' % base_dir
pid_file = '%s/sodd-deamon.pid' % base_dir
stdout_ = '/dev/stdout'
stderr_ = '/dev/stderr'

sodd_daemon = SoddDaemon(pid_file, dir_=chdir_, stdout=stdout_,
                                                stderr=stderr_)

def start_daemon(proj_file):
    """run the sodd as a daemon, proj_file could be 'doit.yaml' or
    'nbet.yaml'. maybe we need to move these files from sodd directory
    to to the root directory.
    """
    print 'starting the sodd daemon...'
    sodd_daemon.set_proj_file(proj_file)
    sodd_daemon.start()
    print 'sodd daemon started.'

def stop_daemon():
    print 'Stoping the sodd daemon...'
    sodd_daemon.stop()
    print 'sodd daemon stopped.'

def status():
    if sodd_daemon.is_run():
        print "It's working"
    else:
        print "NOT WORKING"

def show_help():
    print """usage: sodd_ctl.py <action> [<options>]

actions:
  start:
    start the daemon, also require a `--file` option

  stop:
    stop the daemon

  status:
    check the status of sodd daemon

options:
  --file <filename>:
    identify the yaml file we used in project
"""


def main():
    opts, args = gnu_getopt(sys.argv[1:], '', ['file='])
    if 'start' in args:
        assert not 'stop' in args
        for item in opts:
            if '--file' == item[0]:
                start_daemon(item[1])
                break
        else:
            show_help()
    elif 'stop' in args:
        stop_daemon()
    elif 'status' in args:
        status()
    else:
        show_help()

if __name__ == '__main__':
    main()

