
import py.test
from mock import Mock

from ..scheduler import Task
from ..main import VcsTask, IntegrationTask, JobGroupTask


class TestVcsTask(object):
    def test_run(self):
        code = Mock()
        code.get_new_revisions.return_value = [
            {'revision':'13', 'committer':'e','comment':''},
            {'revision':'15', 'committer':'e','comment':''},]
        vcs_info = {'project': {},
                    'code': code,
                    'source_tree_id': 1,
                    'instance_id': 1}
        task = VcsTask(Mock(),vcs_info)
        task.parent = Mock()
        task.parent.last_rev = '12'

        gen = task.run()
        # get 2 new integration tasks
        integ1 = gen.next()
        assert isinstance(integ1, IntegrationTask)
        integ2 = gen.next()
        assert isinstance(integ2, IntegrationTask)

        py.test.raises(StopIteration, gen.next)
        assert '15' == task.parent.last_rev


class TestIntegrationTask(object):
    def test_run(self):
        code = Mock()
        vcs_info = {'project': {'pre-integration': [],
                                'tasks': ['t1', 't2'],
                                '_pool_path': ''},
                    'code': code,
                    'source_tree_id': 1,
                    'instance_id': 1,
                    }

        intg = IntegrationTask(Mock(), vcs_info, '15', 'ed', '-')
        gen = intg.run()
        # execute 2 job groups
        (group1, pause1) = gen.next()
        assert isinstance(group1, JobGroupTask)
        (group2, pause2) = gen.next()
        assert isinstance(group2, JobGroupTask)
        py.test.raises(StopIteration, gen.next)


class TestJobGroupTask(object):

    def test_result(self):
        jg = JobGroupTask(Mock(), 'tx', 1, 'path/to/integration', 1, '1')
        assert 'success' == jg.get_result([{'result':'success'}])
        assert 'fail' == jg.get_result([{'result':'fail'}])

    def test_run(self):
        jg = JobGroupTask(Mock(), 'tx', 1, 'path/to/integration', 1, '1')
        gen = jg.run()
        # execute DoitUnstable on this group
        (do_task, pause) = gen.next()
        assert isinstance(do_task, Task)
        py.test.raises(StopIteration, gen.next)
