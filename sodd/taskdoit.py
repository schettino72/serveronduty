from __future__ import with_statement

import os
import simplejson

from scheduler import Task, ProcessTask, TaskPause

class DoitUnstable(Task):
    """wrap doit integration with some logic to deal with unstable tests

    every task in doit will be mapped to one job
    @ivar dodo_path (str): path to dodo file
    @ivar base_path (str): path to .doit path
    @ivar doit_task (str): task name
    @ivar timeout (floats): maximum seconds job is allowed to take.
                            if it takes longer it is assumed that in hanged.
    @ivar final_result (dict): final result of the job, there 4 results
                               success, fail, unstable, hang

         - name (str)
         - result (str)
         - out (str)
         - err (str)
         - started (str)
         - elapsed (float)

    """
    def __init__(self, dodo_path, doit_task, base_path=None, timeout=None):
        Task.__init__(self)
        self.dodo_path = dodo_path
        self.base_path = base_path if base_path else os.path.dirname(dodo_path)
        self.doit_task = doit_task
        self.timeout = timeout
        # key: task/job name
        # value: list of results (dict)
        self.final_result = {}


    def calculate_final_results(self, run_results):
        """process results from run_results and add them to final_results
        @param run_results (dict): as returned by doit
        @returns tuple (added_something, to_ignore):
             added_something: false if all results were up-to-date or ignored
             to_ignore (list-str): doit-tasks that should be ignored,
                                   (because they consistently fail)
        """
        added_something = False
        to_ignore = []
        for res in run_results['tasks']:
            print "============>", res['name'], " +++> ", res['result']

            # ignore tasks that were not executed
            if res['result'] in ('up-to-date', 'ignore'):
                continue
            added_something = True

            # executed first time. just add it to the list
            if res['name'] not in self.final_result:
                self.final_result[res['name']] = res
                continue

            # it was executed before...
            # if it fails on previous run
            if self.final_result[res['name']]['result'] == 'fail':
                # task failed again. real failure, ignore it on next run
                if res['result'] == 'fail':
                    to_ignore.append(res['name'])

                # fail on previous run but passed now, mark as unstable.
                # keep output from failure
                else:
                    self.final_result[res['name']]['result'] = 'unstable'
                continue

            # for tasks that are repeated even when successful,
            # save them only in case of failure
            if res['result'] == 'fail':
                self.final_result[res['name']] = res

        return (added_something, to_ignore)



    def run(self):
        result_file = '%s/result.json' % self.base_path
        run_cmd = ['doit', '-f', self.dodo_path,
                   '--reporter', 'json',
                   '--output-file', result_file,
                   '--dir', self.base_path,
                   self.doit_task]
        ignore_cmd = ["doit", "-f", self.dodo_path, "ignore"]

        while True:
            # remove results from previous runs
            if os.path.exists(result_file):
                os.remove(result_file)
            print "doit integration in %s" % self.base_path

            # run and get result
            doit_run_task = ProcessTask(run_cmd, self.timeout)
            (yield (doit_run_task, TaskPause(doit_run_task.tid)))

            # check could not run doit
            if not os.path.exists(result_file):
                self.final_result[self.doit_task] = {
                    'name': self.doit_task, 'result': 'error',
                    'out':doit_run_task.outdata.getvalue(),
                    'err':doit_run_task.errdata.getvalue(),
                    'started': '', 'elapsed':0}
                break

            # read json result
            with open(result_file, 'r') as json_result:
                run_results = simplejson.load(json_result)

            # update results
            added_something, to_ignore = self.calculate_final_results(run_results)
            # ignore (dont repeat) failing tasks
            if to_ignore:
                doit_ignore = ProcessTask(ignore_cmd + to_ignore)
                (yield (doit_ignore, TaskPause(doit_ignore.tid)))

            # exit from loop
            # successful returncode will be zero when all tasks have been run
            # added_something is necessary to get errors that unable tasks to run
            if (doit_run_task.proc.returncode == 0) or (not added_something):
                break
