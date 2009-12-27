import os

from ..scheduler import Scheduler
from ..taskdoit import DoitUnstable


THIS_PATH = os.path.dirname(os.path.abspath(__file__))

class TestDoitUnstable(object):
    dodo_file = os.path.join(THIS_PATH, 'dodo_unstable_ok.py')
    db_file = os.path.join(THIS_PATH, '.doit.db')

    def test_final_results(self):
        job = DoitUnstable('base_path', 'xxx')
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


    def test_run_ok(self):
        if os.path.exists(self.db_file): os.remove(self.db_file)
        job = DoitUnstable(self.dodo_file, 't1', THIS_PATH)
        sched = Scheduler()
        sched.add_task(job)
        sched.loop()
        assert 'fail' == job.final_result['t1']['result']

    def test_run_error(self):
        if os.path.exists(self.db_file): os.remove(self.db_file)
        job = DoitUnstable(self.dodo_file, 'inexistent_task', THIS_PATH)
        sched = Scheduler()
        sched.add_task(job)
        sched.loop()
        assert 'error' == job.final_result['inexistent_task']['result']

