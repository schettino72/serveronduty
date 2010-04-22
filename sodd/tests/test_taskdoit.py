from __future__ import with_statement

import os

import simplejson
import py.test
from mock import Mock

from ..taskdoit import DoitStable, DoitUnstableNoContinue, DoitUnstable
from ..scheduler import ProcessTask, TaskPause

THIS_PATH = os.path.dirname(os.path.abspath(__file__))
DODO_FILE = os.path.join(THIS_PATH, '__dodo__.py') # doesnt really exist
DB_FILE = os.path.join(THIS_PATH, '.doit.db')
SAMPLE_RESULT = {u'err': u'',
                 u'out': u'',
                 u'tasks': [{u'elapsed': 0.066853046417236328,
                             u'err': u'',
                             u'name': u't1',
                             u'out': u"something went wrong\n",
                             u'result': u'fail',
                             u'started': u'2010-04-13 04:16:07.004219'},
                            ]
                 }

class TestCreateDoitTask(object):
    def test_remove_result_file(self):
        job = DoitStable(DODO_FILE, 't1', THIS_PATH)
        # create result file
        rf = open(job.result_file, 'w')
        rf.close()
        assert os.path.exists(job.result_file)
        job.create_doit_task()
        assert not os.path.exists(job.result_file)

    def test_read_json_result_ok(self):
        job = DoitStable(DODO_FILE, 't1', THIS_PATH)
        job.create_doit_task()
        doit_run_task = Mock()
        with open(job.result_file, 'w') as json_result:
            simplejson.dump(SAMPLE_RESULT, json_result)
        got = job.read_json_result(doit_run_task)
        assert SAMPLE_RESULT == got

    def test_read_json_result_no_file(self):
        job = DoitStable(DODO_FILE, 't1', THIS_PATH)
        job.create_doit_task()
        doit_run_task = Mock()
        got = job.read_json_result(doit_run_task)
        assert None == got
        assert 'error' == job.final_result['t1']['result']

    def test_read_json_result_invalid_json(self):
        job = DoitStable(DODO_FILE, 't1', THIS_PATH)
        job.create_doit_task()
        doit_run_task = Mock()
        doit_run_task.errdata.getvalue = Mock(return_value='j')
        with open(job.result_file, 'w') as json_result:
            json_result.write('{Asdfa{:')
        got = job.read_json_result(doit_run_task)
        assert None == got
        assert 'error' == job.final_result['t1']['result']

class TestDoitStable(object):
    def test(self, monkeypatch):
        job = DoitStable(DODO_FILE, 't1', THIS_PATH)
        doit_result = SAMPLE_RESULT
        mock_result = Mock(return_value=doit_result)
        monkeypatch.setattr(job, "read_json_result", mock_result)

        yi = job.run()
        (run, pause) = yi.next()
        assert isinstance(run, ProcessTask)
        assert isinstance(pause, TaskPause)
        py.test.raises(StopIteration, yi.next)
        assert 'fail' == job.final_result['t1']['result']


class TestDoitUnstableNoContinue(object):
    def test_final_results(self):
        job = DoitUnstableNoContinue('base_path', 'xxx')
        assert 0 == len(job.final_result)

        # first batch
        batch1 =[{'name': 'res0', 'result': 'success', 'out':'1'},
                 {'name': 'res1', 'result': 'success'},
                 {'name': 'res2', 'result': 'fail', 'out':'1'},
                 {'name': 'res3', 'result': 'fail'},]
        added, to_ignore = job.calculate_final_results({'tasks': batch1})
        assert 4 == len(job.final_result)
        assert added
        assert 0 == len(to_ignore)

        # second batch
        batch2 = [{'name': 'res0', 'result': 'fail', 'out':'2'},
                  {'name': 'res1', 'result': 'up-to-date'},
                  {'name': 'res2', 'result': 'success', 'out':'2'},
                  {'name': 'res3', 'result': 'fail'},
                  {'name': 'res4', 'result': 'success'},]
        added, to_ignore = job.calculate_final_results({'tasks': batch2})
        assert 5 == len(job.final_result)
        assert added
        assert 1 == len(to_ignore)

        # third batch
        batch3 = [{'name': 'res1', 'result': 'up-to-date'},
                  {'name': 'res2', 'result': 'ignore'},
                  {'name': 'res3', 'result': 'ignore'},]
        added, to_ignore = job.calculate_final_results({'tasks': batch3})
        assert 5 == len(job.final_result)
        assert not added
        assert 0 == len(to_ignore)

        # success, fail = fail
        assert 'fail' == job.final_result['res0']['result']
        assert '2' == job.final_result['res0']['out']

        # success, up-to-date = success
        assert 'success' == job.final_result['res1']['result']

        # fail, success = unstable
        assert 'unstable' == job.final_result['res2']['result']
        assert '1' == job.final_result['res2']['out']

        # fail, fail, ignore = fail
        assert 'fail' == job.final_result['res3']['result']

        # sucess = sucess
        assert 'success' == job.final_result['res4']['result']


    def test_run_with_failures(self, monkeypatch):
        job = DoitUnstableNoContinue(DODO_FILE, 't1', THIS_PATH)
        doit_result = SAMPLE_RESULT
        mock_result = Mock(return_value=doit_result)
        monkeypatch.setattr(job, "read_json_result", mock_result)
        mock_process = Mock()
        mock_process.returncode = 1

        yi = job.run()
        # 1) execute first time
        (run1, pause1) = yi.next()
        assert isinstance(run1, ProcessTask)
        assert 'run' in run1.cmd
        assert isinstance(pause1, TaskPause)
        run1.proc = mock_process
        # 2) execute second time
        (run2, pause2) = yi.next()
        run2.proc = mock_process
        assert 'run' in run2.cmd
        # 3) execute ignore
        (ignore, pause3) = yi.next()
        assert 'ignore' in ignore.cmd
        # final result is fail
        assert 'fail' == job.final_result['t1']['result']

    def test_run_success(self, monkeypatch):
        job = DoitUnstableNoContinue(DODO_FILE, 't1', THIS_PATH)
        doit_result = SAMPLE_RESULT
        mock_result = Mock(return_value=doit_result)
        monkeypatch.setattr(job, "read_json_result", mock_result)
        mock_process = Mock()
        mock_process.returncode = 0 # success (ignore failed on data)

        yi = job.run()
        # 1) execute first time
        (run1, pause1) = yi.next()
        assert isinstance(run1, ProcessTask)
        assert 'run' in run1.cmd
        assert isinstance(pause1, TaskPause)
        run1.proc = mock_process
        py.test.raises(StopIteration, yi.next)

    def test_run_error(self, monkeypatch):
        job = DoitUnstableNoContinue(DODO_FILE, 't1', THIS_PATH)
        doit_result = None
        mock_result = Mock(return_value=doit_result)
        monkeypatch.setattr(job, "read_json_result", mock_result)
        mock_process = Mock()
        mock_process.returncode = 1

        yi = job.run()
        # 1) execute first time
        (run1, pause1) = yi.next()
        run1.proc = mock_process
        # 2) try again
        (run2, pause2) = yi.next()
        run2.proc = mock_process
        # 3 give-up
        py.test.raises(StopIteration, yi.next)


class TestDoitUnstable(object):
    def testContinue(self):
        job = DoitUnstable(DODO_FILE, 't1', THIS_PATH)
        proc = job.create_doit_task()
        assert "--continue" in proc.cmd
