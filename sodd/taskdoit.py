import os
import simplejson

from scheduler import Task, ProcessTask, TaskPause

class DoitUnstable(Task):
    """wrap doit integration with some logic to deal with unstable tests

    every task in doit will be mapped to one job
    """
    def __init__(self, base_path, doit_task, timeout=None):
        Task.__init__(self)
        self.base_path = base_path
        self.doit_task = doit_task
        self.timeout = timeout
        # key: task/job name
        # value: list of results (dict)
        self.final_result = {}


    def _get_json(self, file_path):
        """read json content from file and return as """
        result_file = open(file_path ,'r')
        output = result_file.read()
        result_file.close()
        try:
            try_results = simplejson.loads(output)
        except ValueError, ve:
            print "JSON loading failed: " + output
            raise
        return try_results


    def calculate_final_results(self, run_results):
        """process results from run_results and add them to final_results"""
        added_something = False
        to_ignore = []
        for res in run_results['tasks']:
            print "============>", res['name'], " +++> ", res['result']

            # ignore tasks that were not executed
            if res['result'] in ('up-to-date', 'ignore'):
                continue
            added_something = True

            # execute first time. just add it to the list
            if res['name'] not in self.final_result:
                self.final_result[res['name']] = res
                continue

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
        dodo = '%s/dodo.py' % self.base_path
        run_cmd = ['doit', '-f', dodo, '--reporter', 'json',
                   '--output-file', '%s/result.json' % self.base_path,
                   self.doit_task]
        ignore_cmd = ["doit", "-f", dodo, "ignore"]

        while True:
            # remove results from previous runs
            if os.path.exists('%s/result.json' % self.base_path):
                os.remove('%s/result.json' % self.base_path)
            print "doit integration in %s" % self.base_path

            # run and get result
            doit_run_task = ProcessTask(run_cmd, self.timeout)
            (yield (doit_run_task, TaskPause(doit_run_task.tid)))
            run_results = self._get_json('%s/result.json' % self.base_path)

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
