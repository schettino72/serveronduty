from __future__ import with_statement

import os
import logging
import itertools

import simplejson

from scheduler import Task, ProcessTask, TaskPause


class BaseDoit(Task):
    """
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

        self.result_file = '%s/result.json' % self.base_path
        self.run_options = [('--file', self.dodo_path),
                            ('--reporter', 'json'),
                            ('--output-file', self.result_file),
                            ('--dir', self.base_path)]


    def create_doit_task(self):
        # remove results from previous runs
        if os.path.exists(self.result_file):
            os.remove(self.result_file)
        run_cmd = (['doit', 'run'] + list(itertools.chain(*self.run_options)) +
                   [self.doit_task])
        return ProcessTask(run_cmd, self.timeout)


    def read_json_result(self, doit_run_task):
        """read results from file and return result dictionary

        If there was an error on its execution,
        self.final is update and None is returned.
        """
        # set final_result for task has an error (could not run)
        def set_run_error(error_str=''):
            self.final_result[self.doit_task] = {
                'name': self.doit_task, 'result': 'error',
                'out': doit_run_task.outdata.getvalue(),
                'err': doit_run_task.errdata.getvalue(),
                'started': '', 'elapsed':0}
            if error_str:
                self.final_result[self.doit_task]['err'] += error_str

        # check could not run doit
        if not os.path.exists(self.result_file):
            set_run_error()
            return None

        # read json result
        with open(self.result_file, 'r') as json_result:
            try:
                run_results = simplejson.load(json_result)
            except ValueError, e:
                run_results = None
                set_run_error('\nInvalid json:\n%s\n' % json_result.read())
                logging.error("DOIT execution error.")
                logging.error("%s:%s" % (self.dodo_path, self.doit_task))
                logging.error(e)
        return run_results


class DoitStable(BaseDoit):
    """wrap doit integration"""
    def __init__(self, dodo_path, doit_task, base_path=None, timeout=None):
        BaseDoit.__init__(self, dodo_path, doit_task, base_path, timeout)
        self.run_options.append(('--continue',))

    def run(self):
        doit_run_task = self.create_doit_task()
        (yield (doit_run_task, TaskPause(doit_run_task.tid)))
        run_results = self.read_json_result(doit_run_task)
        if run_results:
            for res in run_results['tasks']:
                self.final_result[res['name']] = res


class DoitUnstableNoContinue(BaseDoit):
    """wrap doit integration with some logic to deal with unstable tests
    Immediately stop on failure and restart tests from failure
    """

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
            # print "============>", res['name'], " +++> ", res['result']
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
        doit_failed = False # doit command failed (invalid json output)
        while True:
            print "doit integration in %s" % self.base_path

            # run and get result
            doit_run_task = self.create_doit_task()
            (yield (doit_run_task, TaskPause(doit_run_task.tid)))

            run_results = self.read_json_result(doit_run_task)
            # error executing doit
            if run_results is None:
                if doit_failed:
                    logging.error("second error, give up.")
                    break
                else:
                    logging.error("retrying...")
                    doit_failed = True
                    continue

            # update results
            added_something, to_ignore = self.calculate_final_results(run_results)

            # ignore (dont repeat) failing tasks
            if to_ignore:
                ignore_cmd = ["doit", "-f", self.dodo_path, "ignore"]
                doit_ignore = ProcessTask(ignore_cmd + to_ignore)
                (yield (doit_ignore, TaskPause(doit_ignore.tid)))

            # exit from loop if finished
            # successful returncode will be zero when all tasks have been run
            # added_something is necessary to get errors that unable tasks to run
            if (doit_run_task.proc.returncode == 0) or (not added_something):
                break


class DoitUnstable(DoitUnstableNoContinue):
    def __init__(self, dodo_path, doit_task, base_path=None, timeout=None):
        DoitUnstableNoContinue.__init__(self, dodo_path, doit_task, base_path,
                                        timeout)
        self.run_options.append(('--continue',))
