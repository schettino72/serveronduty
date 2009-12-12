"""A scheduler that controls the execution of multiple "tasks"
"""

import os
import subprocess
import time
import signal
from collections import deque
import heapq
import logging
import StringIO
from inspect import isfunction, ismethod, CO_GENERATOR

logging.basicConfig(level=logging.DEBUG)



class TaskFinished(object):
    pass


class Task(object):
    """Base for all tasks
    @cvar tid_counter (int): provides an unique "task id" for every task
    @ivar tid (int): task id
    @ivar scheduled (float): seconds since epoch (as given by time.time)

    This class represents an activity that is run controlled by the Scheduler.
    There are two ways to specify the activity: by passing a callable object to
    the constructor, or by overriding the run() method in a subclass.
    The activity function might be a simple method or a coroutine.
    (shameless copied from python threading)
    """

    tid_counter = 0
    def __init__(self, run_method=None):
        Task.tid_counter += 1
        self.tid = Task.tid_counter
        self._started = False # started running
        self._coroutine = False
        self.scheduled = None

        if run_method is not None:
            self.run = run_method
        assert self.run #TODO
        if self.isgeneratorfunction(self.run):
            self._coroutine = self.run()

    def __str__(self):
        return "%s:%s" % (self.__class__.__name__, self.tid)

    def __cmp__(self, other):
        """comparison based on scheduled time"""
        return cmp(self.scheduled, other.scheduled)


    def isgeneratorfunction(self, object):
        """Return true if the object is a user-defined generator function.

        Generator function objects provides same attributes as functions.
        (copied from python2.6 inspect module)
        """
        return bool((isfunction(object) or ismethod(object)) and
                    object.func_code.co_flags & CO_GENERATOR)

    def run_iteration(self):
        if self._coroutine:
            if not self._started:
                self._started = True
                self._coroutine.next()
                return
            assert not self._coroutine.gi_running # TODO: remove this
            try:
                self._coroutine.send(None)
            except StopIteration, e:
                return TaskFinished
        # run is simple function
        else:
            self._started = True
            self.run()
            return TaskFinished


class ProcessTask(Task):
    """A task that executes a shell command"""
    def __init__(self, cmd):
        Task.__init__(self)
        self.cmd = cmd
        self.proc = None
        self.outdata = StringIO.StringIO()
        self.errdata = StringIO.StringIO()

    def __str__(self):
        return Task.__str__(self) + "(%s)" % " ".join(self.cmd)

    def run(self):
        self.proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
        (yield) # wait for self.proc to finish

        # TODO this is getting tricky... and ugly see:
        # http://groups.google.com/group/comp.lang.python/browse_thread/thread/9e19f3a79449f536/
        # try some king of polling? or turn-on / turn-off signal handling...
        # stdout
        while True:
            try:
                buff = self.proc.stdout.read(1024)
                if not buff:
                    break
                self.outdata.write(buff)
            # in case a signal is received while reading proc.stdout
            except IOError:
                pass
        # stderr
        while True:
            try:
                buff = self.proc.stderr.read(1024)
                if not buff:
                    break
                self.errdata.write(buff)
            except IOError:
                pass


    def terminate(self):
        os.kill(self.proc.pid, signal.SIGTERM)


    def get_returncode(self):
        """check if process terminated its execution and get returncode
        @returns (int) returncode or None if process is still running
        """
        if not self._started:
            return None
        try:
            pid, status = os.waitpid(self.proc.pid, os.WNOHANG)
            # Python bug #2475
            # you can not get the returncode twice !
            self.proc.returncode = status
        except OSError:
            # system call can't find pid. it's gone. ignore it
            pass
        return self.proc.returncode




class PidTask(Task):
    """find ProcessTask from pid"""

    def __init__(self, sched):
        Task.__init__(self)
        self.sched = sched

    def run(self):
        for t in self.sched.tasks.itervalues():
            if not isinstance(t, ProcessTask):
                continue
            returncode = t.get_returncode()
            if returncode is not None:
                self.sched.ready.append(t)



class Scheduler(object):
    time = time # time / sleep provider

    def __init__(self, use_sigchld=True):
        self.tasks = {}
        # TODO use Queue (thread-safe)
        self.ready = deque() # ready to execute tasks
        self.waiting = [] # scheduled to be executed in the future
        if use_sigchld:
            self._register_sigchld()

    def _register_sigchld(self):
        # create a task to identify terminated process tid
        def handle_child_terminate(signum, frame):
            self.add_task(PidTask(self))
        signal.signal(signal.SIGCHLD, handle_child_terminate)


    def add_task(self, task, delay=0):
        self.tasks[task.tid] = task
        if delay == 0:
            self.ready.append(task)
        else:
            task.scheduled = self.time.time() + delay
            heapq.heappush(self.waiting, task)


    def run_task(self, task):
        logging.info("%s \t running" % task)
        if task.run_iteration() == TaskFinished:
            del self.tasks[task.tid]


    def loop(self):
        """loop until there are no more active tasks"""
        while self.tasks:
            self.loop_iteration()

    def loop_iteration(self):
        now = self.time.time()

        # add scheduled tasks
        while self.waiting and (self.waiting[0].scheduled <= now):
            self.ready.append(heapq.heappop(self.waiting))

        # execute tasks that are ready to be executed
        if self.ready:
            task = self.ready.popleft()
            self.run_task(task)
            return # just sleep if no task was run

        # wait for until next scheduled task is ready
        # TODO pause if (not self.waiting) ?
        interval = (self.waiting[0].scheduled - now) if self.waiting else 60
        logging.debug("sleeping %s" % interval)
        self.time.sleep(interval)


# TODO
#  stop process timeout
#  periodic task
#  task locks
#
#  RPC/webserver
#  threaded task
#  async db
#  pause/resume
