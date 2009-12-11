import os
import time

from scheduler import TaskFinished, BaseTask, ProcessTask, PidTask


class TestTask(object):
    def test_tid(self):
        t1 = BaseTask()
        t2 = BaseTask()
        assert (t1.tid + 1) == t2.tid

    def test_str(self):
        t1 = BaseTask()
        assert "BaseTask" in str(t1)
        assert str(t1.tid) in str(t1)

    def test_cmp(self):
        t1 = BaseTask()
        t2 = BaseTask()
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
        t1.run()
        while(t1.proc.poll() is None):
            time.sleep(0.02) # magic number :)
        assert t1.outdata is None
        # second run does data post-processing, and finishes task
        got = t1.run()
        assert TaskFinished == got
        assert "done" == t1.outdata.strip()

    def test_terminate(self):
        t1 = ProcessTask(['python', 'sample1.py', '5'])
        t1.run()
        t1.terminate()
        while(t1.proc.poll() is None):
            time.sleep(0.02) # magic number :)
        # terminating the process does not cancel its post processing
        t1.run()
        assert 0 != t1.proc.returncode
        assert "" == t1.outdata.strip()

    def test_get_returncode(self, monkeypatch):
        monkeypatch.setattr(os, 'waitpid', lambda pid, opt: (pid, 0))
        t1 = ProcessTask(['python', 'sample1.py', '0'])
        # not started
        assert None == t1.get_returncode()
        t1.run()
        # done
        assert 0 == t1.get_returncode()

    def test_get_returncode_exception(self, monkeypatch):
        # raised expection
        def do_raise(pid, opt):
            raise OSError()
        monkeypatch.setattr(os, 'waitpid', do_raise)
        t1 = ProcessTask(['python', 'sample1.py', '0'])
        t1.run()
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
            fake_sched.tasks['1'] = BaseTask()
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
        assert TaskFinished == t1.run()
        assert [fake_sched.tasks['2']] == t1.sched.ready


class Mocktime(object):
    def __init__(self):
        self.current = 0
    def time(self):
        return self.current
    def sleep(self, delay):
        self.current += delay


