import os
import time
import signal

from scheduler import TaskFinished, Task, ProcessTask, PidTask
from scheduler import Scheduler


class MockTime(object):
    def __init__(self):
        self.current = 0
    def time(self):
        return self.current
    def sleep(self, delay):
        self.current += delay


class TestTask(object):
    def test_tid(self):
        t1 = Task(lambda :None)
        t2 = Task(lambda :None)
        assert (t1.tid + 1) == t2.tid

    def test_str(self):
        t1 = Task(lambda :None)
        assert "Task" in str(t1)
        assert str(t1.tid) in str(t1)

    def test_cmp(self):
        t1 = Task(lambda :None)
        t2 = Task(lambda :None)
        # None None
        assert not (t1 < t2)
        assert not (t1 > t2)
        # 3 None
        t1.scheduled = 3
        assert not (t1 < t2)
        assert (t1 > t2)
        # 3 3.5
        t2.scheduled = 5
        assert (t1 < t2)
        assert not (t1 > t2)

    def test_run_function(self):
        t1 = Task(lambda :None)
        assert isinstance(t1.run_iteration(), TaskFinished)

    def test_run_coroutine(self):
        def sample_coroutine():
            x = 5
            (yield x)
            x += 3
        t1 = Task(sample_coroutine)
        assert 5 == t1.run_iteration()
        assert isinstance(t1.run_iteration(), TaskFinished)


class TestProcessTask(object):
    def test_str(self):
        t1 = ProcessTask(['python', 'xxx.py'])
        assert "ProcessTask" in str(t1)
        assert str(t1.tid) in str(t1)
        assert "python xxx" in str(t1)

    def test_run(self):
        t1 = ProcessTask(['python', 'sample1.py', '0'])
        # not started yet
        assert t1.proc is None
        # first run starts the process
        got = t1.run_iteration()
        assert got is None
        while(t1.proc.poll() is None): time.sleep(0.02) # magic number :)
        assert "" == t1.outdata.getvalue()
        # second run does data post-processing, and finishes task
        assert isinstance(t1.run_iteration(), TaskFinished)
        assert "done" == t1.outdata.getvalue().strip()

    def test_timeout(self, monkeypatch):
        mytime = MockTime()
        monkeypatch.setattr(time, 'time', mytime.time)
        timeout = 30
        t1 = ProcessTask(['python', 'sample1.py', '0'], 30)
        # not started yet
        assert t1.proc is None
        # first run starts the process
        got = t1.run_iteration()
        assert isinstance(got, Task)
        assert got.scheduled == (time.time() + timeout)
        t1.terminate() #cleanup

    def test_terminate(self):
        t1 = ProcessTask(['python', 'sample1.py', '5'])
        t1.run_iteration()
        t1.terminate()
        while(t1.proc.poll() is None):
            time.sleep(0.02) # magic number :)
        # terminating the process does not cancel its post processing
        t1.run_iteration()
        assert 0 != t1.proc.returncode

    def test_get_returncode(self, monkeypatch):
        monkeypatch.setattr(os, 'waitpid', lambda pid, opt: (pid, 0))
        t1 = ProcessTask(['python', 'sample1.py', '0'])
        # not started
        assert None == t1.get_returncode()
        t1.run_iteration()
        # done
        assert 0 == t1.get_returncode()

    def test_get_returncode_exception(self, monkeypatch):
        # raised expection
        def do_raise(pid, opt):
            raise OSError()
        monkeypatch.setattr(os, 'waitpid', do_raise)
        t1 = ProcessTask(['python', 'sample1.py', '0'])
        t1.run_iteration()
        assert None == t1.get_returncode()


class TestPidTask(object):
    def pytest_funcarg__fake_sched(self, request):
        def fake_sched():
            class Empty(object): pass
            fake_sched = Empty()
            fake_sched.tasks = {}
            fake_sched.ready = []
            finished = ProcessTask(['xxx'])
            finished._started = True
            finished.get_returncode = lambda :0
            not_finished = ProcessTask(['xxx'])
            not_finished._started = True
            not_finished.get_returncode = lambda :None
            fake_sched.tasks['1'] = Task(lambda :None)
            fake_sched.tasks['2'] = finished
            fake_sched.tasks['3'] = not_finished
            return fake_sched
        return request.cached_setup(setup=fake_sched, scope="function")

    def test_str(self, fake_sched):
        t1 = PidTask(fake_sched)
        assert "PidTask" in str(t1)
        assert str(t1.tid) in str(t1)

    def test_run(self, fake_sched):
        t1 = PidTask(fake_sched)
        assert isinstance(t1.run_iteration(), TaskFinished)
        assert [fake_sched.tasks['2']] == t1.sched.ready


# ################################# Scheduler

def pytest_funcarg__sched(request):
    # scheduler with fake(controlled) time functions
    def fake_sched():
        return Scheduler(False)
    return request.cached_setup(setup=fake_sched, scope="function")

class TestScheduler(object):
    def test_child_terminate(self):
        sched = Scheduler()
        assert 0 == len(sched.tasks)
        os.kill(os.getpid(), signal.SIGCHLD)
        assert 1 == len(sched.tasks)
        assert isinstance(sched.tasks.values()[0], PidTask)
        # restore default
        signal.signal(signal.SIGCHLD, signal.SIG_DFL)
        os.kill(os.getpid(), signal.SIGCHLD)
        assert 1 == len(sched.tasks)


    def test_add_task_ready(self, sched):
        t1 = Task(lambda :None)
        sched.add_task(t1)
        assert 1 == len(sched.tasks)
        assert t1 == sched.tasks[t1.tid]
        assert 1 == len(sched.ready)
        assert 0 == len(sched.waiting)

    def test_add_task_scheduled_delay(self, sched):
        tasks = [Task(lambda :None) for i in range(3)]
        sched.add_task(tasks[0], 20)
        sched.add_task(tasks[1], 1)
        sched.add_task(tasks[2], 10)
        assert 3 == len(sched.tasks)
        assert 0 == len(sched.ready)
        assert 3 == len(sched.waiting)
        # first element of waitng must be the next to be executed
        assert tasks[1] == sched.waiting[0]

    def test_add_task_scheduled_timestamp(self, sched):
        t1 = Task((lambda :None), 300)
        sched.add_task(t1)
        assert 1 == len(sched.tasks)
        assert 0 == len(sched.ready)
        assert 1 == len(sched.waiting)
        assert t1 == sched.waiting[0]

    def test_run_task(self, sched):
        t2 = Task(lambda :None)
        t1 = Task(lambda :(yield t2))
        # just t1
        sched.add_task(t1)
        assert 1 == len(sched.tasks)
        # t1 added t2
        sched.run_task(t1)
        assert 2 == len(sched.tasks)
        # t2 finished and removed
        sched.run_task(t2)
        assert 1 == len(sched.tasks)


class TestSchedulerPool(object):

    def test_iteration_execute_one(self, sched):
        sched.add_task(Task(lambda :None))
        sched.add_task(Task(lambda :None))
        sched.loop_iteration()
        assert 1 == len(sched.ready)

    def test_iteration_waiting(self, sched, monkeypatch):
        mytime = MockTime()
        monkeypatch.setattr(time, 'time', mytime.time)
        t1 = Task(lambda :None)
        t2 = Task(lambda :None)
        t3 = Task(lambda :None)
        sched.add_task(t1)
        sched.add_task(t2, 40)
        sched.add_task(t3, 30)
        mytime.current += 35
        sched.loop_iteration()
        assert t3 == sched.ready[0]
        assert t2 == sched.waiting[0]

    def test_iteration_sleep(self, sched, monkeypatch):
        mytime = MockTime()
        monkeypatch.setattr(time, 'time', mytime.time)
        monkeypatch.setattr(time, 'sleep', mytime.sleep)
        t1 = Task(Task(lambda :None))
        mytime.current = 100
        sched.add_task(t1, 40)
        sched.loop_iteration()
        assert 140 == mytime.current

    def test_loop_no_tasks(self, sched):
        def not_executed(): raise Exception('this must not be executed')
        sched.loop_iteration = not_executed
        sched.loop()
        # nothing raised ok

    def test_loop_with_tasks(self, sched):
        count = [] # count how many tasks were executed
        def count_run():
            count.append(1)
        t1 = Task(count_run)
        t2 = Task(count_run)
        sched.add_task(t1)
        sched.add_task(t2)
        sched.loop()
        assert 2 == len(count)
