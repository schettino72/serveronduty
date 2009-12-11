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


logging.basicConfig(level=logging.DEBUG)



class TaskFinished(object):
    pass


class BaseTask(object):
    """Base for all tasks
    @cvar tid_counter (int): provides an unique "task id" for every task
    @ivar tid (int): task id
    @ivar scheduled (float): seconds since epoch (as given by time.time)
    """

    tid_counter = 0
    def __init__(self):
        BaseTask.tid_counter += 1
        self.tid = BaseTask.tid_counter
        self.scheduled = None

    def __str__(self):
        return "%s:%s" % (self.__class__.__name__, self.tid)

    def __cmp__(self, other):
        """comparison based on scheduled time"""
        return cmp(self.scheduled, other.scheduled)


class ProcessTask(BaseTask):
    """ """
    def __init__(self, cmd):
        BaseTask.__init__(self)
        self.cmd = cmd
        self.proc = None
        self._coroutine = self._coroutine_loop()
        self._started = False # started process
        self.outdata = StringIO.StringIO()
        self.errdata = StringIO.StringIO()

    def __str__(self):
        return BaseTask.__str__(self) + "(%s)" % " ".join(self.cmd)

    def run(self):
        if not self._started:
            self._started = True
            self._coroutine.next()
            return
        assert not self._coroutine.gi_running
        try:
            self._coroutine.send(None)
        except StopIteration, e:
            return TaskFinished

    def _coroutine_loop(self):
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
            except IOError:
                pass # in case a signal is received while reading proc.stdout
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




class PidTask(BaseTask):
    """find tasks from pid's"""

    def __init__(self, sched):
        BaseTask.__init__(self)
        self.sched = sched

    def run(self):
        for t in self.sched.tasks.itervalues():
            if not isinstance(t, ProcessTask):
                continue
            returncode = t.get_returncode()
            if returncode is not None:
                self.sched.ready.append(t)
        return TaskFinished



class Scheduler(object):
    time = time # time / sleep provider

    def __init__(self):
        self.tasks = {}
        # TODO use Queue (thread-safe)
        self.ready = deque() # ready to execute tasks
        self.waiting = [] # scheduled to be executed in the future

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
        if task.run() == TaskFinished:
            del self.tasks[task.tid]


    def loop(self):
        # loop until there are no more active tasks
        while self.tasks:
            # add scheduled tasks
            now = self.time.time()

            # add scheduled tasks
            while self.waiting and (self.waiting[0].scheduled <= now):
                self.ready.append(heapq.heappop(self.waiting))

            # execute tasks that are ready to be executed
            if self.ready:
                task = self.ready.popleft()
                self.run_task(task)
                continue # just sleep if no task was run

            # wait for until next scheduled task is ready
            # TODO pause if (not self.waiting) ?
            interval = (self.waiting[0].scheduled - now) if self.waiting else 60
            logging.debug("sleeping %s" % interval)
            self.time.sleep(interval)



if __name__ == "__main__":
    sched = Scheduler()
    sched.add_task(ProcessTask(['echo', 'xx']))
    sched.add_task(ProcessTask(['python', 'sample1.py', '1']))
    time.sleep(2.5)
    sched.add_task(ProcessTask(['python', 'sample1.py', '2']))
    sched.add_task(ProcessTask(['echo', 'xx']), 10)
    sched.loop()


# TODO
# stop process timeout
# periodic task
# task locks
# threaded task
# async db
# RPC
# pause/resume
