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


# logging
logging.basicConfig(level=logging.DEBUG, format="%(message)s")


# commands passed from task to scheduler
class TaskFinished(object):
    """indicate this task has finished"""
    pass

class TaskSleep(object):
    """sleep current task until scheduled time """
    pass

#TODO: merge sleep/pause
class TaskPause(object):
    """Pause current task until given task terminates """
    def __init__(self, tid=None):
        self.tid = tid

class TaskCancel(object):
    """Cancel task"""
    def __init__(self, tid):
        self.tid = tid

###################################################

class Task(object):
    """Base for all tasks
    @cvar tid_counter (int): provides an unique "task id" for every task
    @ivar tid (int): task id
    @ivar scheduled (float): when this task should be executed,
                             in seconds since epoch (as given by time.time)
    @ivar lock (str): name of the lock this task holds while running
    @ivar dependents (list - int): list of tasks that are waitng for this
                                   task to be finished.

    This class represents an activity that is run controlled by the Scheduler.
    There are two ways to specify the activity: by passing a callable object to
    the constructor, or by overriding the run() method in a subclass.
    The activity function might be a simple method or a coroutine.
    (shameless copied from python threading)
    """

    tid_counter = 0
    def __init__(self, run_method=None, scheduled=None, lock=None):
        Task.tid_counter += 1
        self.tid = Task.tid_counter
        self.scheduled = scheduled
        self.lock = lock
        self.dependents = []

        if run_method is not None:
            self.run = run_method
        assert self.run #TODO


        self._coroutine = None
        if self.isgeneratorfunction(self.run):
            self._coroutine = self.run()

        self._started = False # started running
        self.cancelled = False


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
        if self.cancelled:
            return TaskFinished()

        if self._coroutine:
            if not self._started:
                self._started = True
                return self._coroutine.next()
            assert not self._coroutine.gi_running # TODO: remove this
            try:
                # TODO: can i just use next?
                return self._coroutine.send(None)
            except StopIteration, e:
                return TaskFinished()
        # run is simple function
        else:
            self._started = True
            self.run()
            return TaskFinished()



class PeriodicTask(Task):
    def __init__(self, interval, task_class, *args, **kwargs):
        Task.__init__(self)
        self.interval = interval
        self.task_class = task_class
        self.args = args
        self.kwargs = kwargs

    def run(self):
        while True:
            now = time.time()
            next_iteration = now + self.interval
            # TODO: take last time executed into consideration!
            new_task = self.task_class(*self.args, **self.kwargs)
            new_task.scheduled = next_iteration
            self.scheduled = next_iteration
            yield (new_task, TaskSleep())



class ProcessTask(Task):
    """A task that executes a shell command"""
    def __init__(self, cmd, timeout=None, lock=None):
        """
        @param cmd (list): list of strings for Popen
        @param timeout (float): time in seconds for terminating the process
        """
        Task.__init__(self, lock=lock)
        self.cmd = cmd
        self.proc = None
        self.outdata = StringIO.StringIO()
        self.errdata = StringIO.StringIO()
        self.timeout = timeout

    def __str__(self):
        return Task.__str__(self) + "(%s)" % " ".join(self.cmd)

    def run(self):
        self.proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)

        # wait for self.proc to finish
        sched_operations = [TaskPause()]
        timeout_task = None
        if self.timeout:
            now = time.time()
            timeout_task = Task(self.terminate, now + self.timeout)
            sched_operations.append(timeout_task)
        yield sched_operations
        # cancel timeout task
        if timeout_task:
            yield TaskCancel(timeout_task.tid)

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
        # TODO: check if sigterm really terminate the process, if not sigkill
        if self.proc.returncode is not None:
            return
        logging.info("SIGTERM %s" % self.proc.pid)

        try:
            os.kill(self.proc.pid, signal.SIGTERM)
        except OSError:
            pass # probably process already terminated. ignore.


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
            if pid:
                self.proc.returncode = status
                logging.debug( "Process pid:%s tid:%s terminated satus:%s" %
                               (pid, self.tid, status))
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



class GroupTask(Task):
    """Execute group of tasks in sequence (one at a time)"""
    def __init__(self, task_list):
        Task.__init__(self)
        self.task_list = task_list[::-1] #reverse list

    def run(self):
        while self.task_list:
            task = self.task_list.pop()
            (yield (task, TaskPause(task.tid)))


class Scheduler(object):
    def __init__(self, use_sigchld=True):
        self.tasks = {}
        # TODO use Queue (thread-safe)
        self.ready = deque() # ready to execute tasks
        self.waiting = [] # scheduled to be executed in the future
        self.locks = {}
        if use_sigchld:
            self._register_sigchld()


    def _register_sigchld(self):
        # create a task to identify terminated process tid
        def handle_child_terminate(signum, frame):
            self.add_task(PidTask(self))
        signal.signal(signal.SIGCHLD, handle_child_terminate)


    def add_task(self, task, delay=0):
        """delay == 0 => ready
           delay < 0 => not ready
           delay > 0 => scheduled
         """
        self.tasks[task.tid] = task
        # set scheduled time
        if delay > 0:
            task.scheduled = time.time() + delay
        elif delay < 0:
            task.scheduled = None
        # ready/schedule/wait
        if delay == 0 and (task.scheduled is None):
            self.ready.append(task)
        elif task.scheduled:
            self.sleep_task(task)


    def sleep_task(self, task):
        # can not be called by a task in ready queue
        # FIXME raise error
        heapq.heappush(self.waiting, task)


    def run_task(self, task):
        # note task should be pop-out of ready queue before calling this

        if (not task._started) and task.lock:
            # locked can't execute now
            if task.lock in self.locks:
                self.locks[task.lock].append(task)
                logging.info("%s \t locked" % task)
                return
            # lock other and start
            self.locks[task.lock] = deque()

        logging.info("%s \t running" % task)

        operations = task.run_iteration()
        # make sure return value is iterable
        if not hasattr(operations, '__iter__'):
            operations = (operations,)

        reschedule = True # add task to ready queue again
        for op in operations:
            # got a new task
            if isinstance(op, Task):
                self.add_task(op)
            # task finished remove it from scheduler
            elif isinstance(op, TaskFinished):
                reschedule = False
                if task.lock:
                    lock_list = self.locks[task.lock]
                    while lock_list:
                        self.ready.append(lock_list.popleft())
                    del self.locks[task.lock]
                for dependent_tid in task.dependents:
                    self.ready.append(self.tasks[dependent_tid])
                del self.tasks[task.tid]
            # sleep
            elif isinstance(op, TaskSleep):
                reschedule = False
                self.sleep_task(task)
            # pause
            elif isinstance(op, TaskPause):
                reschedule = False
                if op.tid is not None:
                    self.tasks[op.tid].dependents.append(task.tid)
            # cancel
            elif isinstance(op, TaskCancel):
                if op.tid in self.tasks:
                    self.tasks[op.tid].cancelled = True
            # do nothing
            elif op is not None:
                raise Exception("returned invalid value %s" % op)
        if reschedule:
            self.ready.append(task)


    def loop(self):
        """loop until there are no more active tasks"""
        while self.tasks:
            self.loop_iteration()


    def loop_iteration(self):
        now = time.time()

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
        time.sleep(interval)


# TODO
#  RPC/webserver
#  threaded task
#  async db
#  pause/resume