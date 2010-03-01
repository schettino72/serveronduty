"""ServerOnDuty daemon aka sodd"""
import os
import shutil
import time
import datetime
import sqlite3
import logging

import yaml

import vcs
from scheduler import Task, PeriodicTask, TaskPause, Scheduler
from taskdoit import DoitUnstable
from litemodel import (save_sodd_instance, save_source_tree_root,
                       save_integration, save_job_group, save_job,
                       update_job_group, update_integration)

# TODO: configuration entry for this
# base pool path where revision will be saved and integration be executed
base_path = os.path.abspath('pool/')

TASK_TIMEOUT = 60 * 60

class VcsTask(Task):
    """check for new revisions on a repository and schedule integration tasks
    """
    def __init__(self, stuff):
        # FIXME document stuff
        Task.__init__(self)
        self.stuff = stuff
        self.code = stuff['code']

    def run(self):
        revs = self.code.get_new_revisions(self.parent.last_rev)
        for a_rev in revs:
            logging.info("*** VcsTask got rev: %s" % a_rev['revision'])
            yield IntegrationTask(self.stuff, a_rev['revision'],
                      a_rev['committer'], a_rev['comment'], lock="integration")
        if(revs):
            self.parent.last_rev = revs[-1]['revision']


class IntegrationTask(Task):
    def __init__(self, stuff, revision, committer, comment, lock=None):
        name = "r%s" % revision
        Task.__init__(self, lock=lock, name=name)
        self.conn = stuff['conn']
        self.project = stuff['project']
        self.code = stuff['code']
        self.source_tree_id = stuff['source_tree_id']
        self.instance_id = stuff['instance_id']

        self.revision = revision
        self.committer = committer
        self.comment = comment


    def run(self):
        integration_id = save_integration(
            self.conn.cursor(), self.revision, 'running', 'unknown',
            self.committer, self.comment, self.source_tree_id)

        # export revision to be tested
        integration_path = base_path + '/' + self.revision
        self.code.archive(self.revision, integration_path)
        # FIXME NBET stuff
        #shutil.copy(base_path + "/dodo.py", integration_path + "/dodo.py")
        #shutil.copy(integration_path + '/local_config.py.DEVELOPER',
        #             integration_path + '/local_config.py')


        integration_result = 'success'
        for task in self.project['tasks']:
            job_task = JobGroupTask(self.conn, task, integration_id,
                        integration_path, self.instance_id, self.name)
            (yield (job_task, TaskPause(job_task.tid)))
            if job_task.group_result != 'success':
                integration_result = 'fail'


        logging.info("*** IntegrationTask %s finished" % self.revision)
        update_integration(self.conn.cursor(), integration_id,
                           integration_result)



class JobGroupTask(Task):
    def __init__(self, conn, task_name, integration_id, integration_path,
                 instance_id, rev_str):
        name = "%s.%s" % (rev_str, task_name)
        Task.__init__(self, name=name)
        self.conn = conn
        self.task_name = task_name
        self.integration_id = integration_id
        self.integration_path = integration_path
        self.instance_id = instance_id
        self.group_result = None


    def run(self):
        self.group_result = 'success' # optimistic

        started_on = time.time()
        started = datetime.datetime.utcfromtimestamp(started_on)

        group_id = save_job_group(self.conn.cursor(), started, 'unknown',
                                  'running', 'unknown', '',
                                  self.integration_id, self.instance_id)

        dodo_path = os.path.join(self.integration_path, 'dodo.py')
        doit_task = DoitUnstable(dodo_path, self.task_name,
                                 timeout=TASK_TIMEOUT)
        doit_task.name = self.name
        (yield (doit_task, TaskPause(doit_task.tid)))
        json_result = doit_task.final_result.values()

        #result = simplejson.loads(json_result)
        save_job(self.conn.cursor(), json_result, self.task_name, group_id)

        # check result of this job group
        for each in json_result:
            if each['result'] != 'success':
                self.group_result = 'fail'
                break

        elapsed = time.time() - started_on
        update_job_group(self.conn.cursor(), group_id, elapsed,
                         self.group_result, '')




def main(project_file):
    project = yaml.load(open(project_file))
    if not os.path.exists("sod.db"):
        logging.error("Can not find DB file sod.db")
        return 1
    conn = sqlite3.connect("sod.db")

    ## register self in sodd_instance table
    ## TODO seems need a rule to name sodd and machine
    instance_id = save_sodd_instance(conn.cursor(), 'SODD 1', 'qtest')

    #if pool is an existing file, that is an error
    if os.path.isfile(base_path):
        raise Exception("pool exists and is a file")
    #if the directory does not exist create it
    if not os.path.isdir(base_path):
        os.mkdir(base_path)

    # insert into source_location table
    source_tree_id = save_source_tree_root(conn.cursor(), project['url'])

    if os.path.exists('trunk'):
        shutil.rmtree('trunk')
    code = vcs.get_vcs(project['vcs'], project['url'], 'trunk')
    code.clone()

    # go go go
    stuff = {'conn':conn,
             'project':project,
             'code':code,
             'source_tree_id':source_tree_id,
             'instance_id':instance_id}
    loop_vcs = PeriodicTask(60, VcsTask, [stuff], name="Check trunk")
    loop_vcs.last_rev = project['start_rev']

    sched = Scheduler()
    sched.add_task(loop_vcs)
    sched.loop()




if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print 'usage: python sodd.py <project.yaml>'
    proj_file = sys.argv[1]
    main(proj_file)
