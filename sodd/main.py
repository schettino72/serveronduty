"""ServerOnDuty daemon aka sodd"""
import sys
import os
import shutil
import time
import datetime
import logging
import urllib2

from sodd import vcs
from sodd.scheduler import Task, PeriodicTask, TaskPause, Scheduler
from sodd.taskdoit import DoitUnstable
from sodd.litemodel import save_sodd_instance, save_source_tree_root
from sodd.litemodel import save_integration, get_last_revision_id
from sodd.litemodel import db_job_group_start, db_job_group_finish, save_job

TASK_TIMEOUT = 60 * 60

class VcsTask(Task):
    """check for new revisions on a repository (polling)
    and create integration tasks

    @ivar conn: a DB connection
    @ivar vcs_info (dict): info from source-code repository. items:
         * project (dict): project cofing
         * code: a repository instance (see vcs.py)
         * source_tree_id (int): internal DB id for repository
                                 (source_tree_root_table)
         * instance_id (int): id for sodd instance (sodd_instance_table)
    """
    def __init__(self, conn, vcs_info):
        Task.__init__(self)
        self.conn = conn
        self.vcs_info = vcs_info

    def run(self):
        # poll
        revs = self.vcs_info['code'].get_new_revisions(self.parent.last_rev)
        # create integration tasks
        for a_rev in revs:
            logging.info("*** VcsTask got rev: %s" % a_rev['revision'])
            yield IntegrationTask(self.conn, self.vcs_info, a_rev['revision'],
                      a_rev['committer'], a_rev['comment'], lock="integration")
        # update parent Task last_rev attribute
        if(revs):
            self.parent.last_rev = revs[-1]['revision']


class IntegrationTask(Task):
    def __init__(self, conn, vcs_info, revision, committer, comment, lock=None):
        name = "r%s" % revision
        Task.__init__(self, lock=lock, name=name)
        self.conn = conn
        self.project = vcs_info['project']
        self.code = vcs_info['code']
        self.source_tree_id = vcs_info['source_tree_id']
        self.instance_id = vcs_info['instance_id']

        self.revision = revision
        self.committer = committer
        self.comment = comment


    def execute_pre_integration(self, integration_path, pre_list):
        """execute pre-integration steps
        @param pre_list: list of strings, each item is
                       <module-name>:<function-name>
        where function takes one paramter (this IntegrationTask object)
        """
        # add current working directory to sys.path
        cwd = os.path.abspath(os.getcwd())
        sys.path.insert(0, cwd)
        for setup in pre_list:
            module_name, fun_name = setup.split(':')
            module = __import__(module_name)
            function = getattr(module, fun_name)
            function(integration_path, self)


    def run(self):
        # save integration started on DB
        integration_id = save_integration(
            self.conn.cursor(), self.revision, 'running', 'unknown',
            self.committer, self.comment, self.source_tree_id)

        # export source-code on revision to be tested
        integration_path = os.path.join(self.project['_pool_path'],
                                        self.revision)
        self.code.archive(self.revision, integration_path)

        self.execute_pre_integration(integration_path,
                                     self.project['pre-integration'])

        # execute integrations
        for task in self.project['tasks']:
            job_task = JobGroupTask(self.conn, task, integration_id,
                        integration_path, self.instance_id, self.name)
            (yield (job_task, TaskPause(job_task.tid)))

        # log
        logging.info("*** IntegrationTask %s finished" % self.revision)

        # notify websod this integration is done
        if 'websod' in self.project:
            websod_url = "%s/group_finished/%s" % (self.project['websod'],
                                                   integration_id)
            try:
                urllib2.urlopen(websod_url)
            except urllib2.URLError, exception:
                msg = "Error notifying websod (%s). %s"
                logging.warning(msg % (websod_url, str(exception)))



class JobGroupTask(Task):
    """JobGroup is a task as specified in a config (yaml) file.
    The group is composed of different jobs (each job is "task" from doit.
    """
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

    def get_result(self, jobs_result):
        """get group result from jobs result
        @return (str): can only be 'success' or 'fail'
        """
        for each in jobs_result:
            if each['result'] != 'success':
                return 'fail'
        return 'success'

    def run(self):
        """Execute task and save result in DB

        workflow
        ---------
         * state: 'running' -> 'finished'
         * result: 'unknown' -> ['fail', 'success']
        """
        # save job_group in DB
        started_on = time.time()
        started = datetime.datetime.utcfromtimestamp(started_on)
        group_id = db_job_group_start(self.conn.cursor(), started, None,
                                  'running', 'unknown', '',
                                  self.integration_id, self.instance_id)

        # excute
        dodo_path = os.path.join(self.integration_path, 'dodo.py')
        doit_task = DoitUnstable(dodo_path, self.task_name,
                                 timeout=TASK_TIMEOUT)
        doit_task.name = self.name
        (yield (doit_task, TaskPause(doit_task.tid)))

        # save jobs result on DB
        jobs_result = doit_task.final_result.values()
        save_job(self.conn.cursor(), jobs_result, self.task_name, group_id)

        # update (finished) job_group on DB
        group_result = self.get_result(jobs_result)
        self.group_result = group_result # FIXME remove this
        elapsed = time.time() - started_on
        db_job_group_finish(self.conn.cursor(), group_id, elapsed,
                         group_result, '') # FIXME log always empty!




def get_db_conn(driver='', username='', password='', host='', port='', database=''):
    """get a DB connection"""
    assert driver
    import dbapiext
    # dbapiext.debug_convert = True

    # SQLITE
    if driver == 'sqlite':
        import sqlite3
        dbapiext.set_paramstyle(sqlite3)
        conn = sqlite3.connect(database)

    # POSTGRES
    elif driver == 'postgres':
        import psycopg2
        dbapiext.set_paramstyle(psycopg2)
        conn = psycopg2.connect("dbname=%s user=%s password=%s host=%s port=%s" %
                                (database, username, password, host, port))

    # ???
    else:
        raise Exception("Sorry DB %s not supported" % driver)

    return conn


def run_ci(base_path, project):
    """ Run Continuous Integration System
     * A periodic task will poll a VCS to get new revisions
     * New IntegrationTask's are created for every new changeset
     @param project (dict): config options for the project
    """
    os.chdir(base_path)

    conn = get_db_conn(**project['db'])

    # check required config values:
    assert 'url' in project
    assert 'vcs' in project
    assert 'tasks' in project
    assert 'start_rev' in project # TODO should be optional
    # pre-integration item must be "<module-name>:<function-name>"
    if 'pre-integration' not in project:
        project['pre-integration'] = []
    # other optional config:
    #  * email_to, email_from
    #  * websod URL to websod instance

    # TODO: configuration entry for this
    # base pool path where revision will be saved and integration be executed
    project['_pool_path'] = os.path.join(base_path, 'pool')


    # if pool is an existing file, that is an error
    if os.path.isfile(project['_pool_path']):
        raise Exception("pool exists and is a file")
    # if the directory does not exist create it
    if not os.path.isdir(project['_pool_path']):
        os.mkdir(project['_pool_path'])


    ## register self in sodd_instance table
    ## TODO get name from yaml config file
    instance_id = save_sodd_instance(conn.cursor(), 'SODD 1', 'qtest')

    # insert into source_location table
    source_tree_id = save_source_tree_root(conn.cursor(), project['url'])


    # clone source-code
    logging.info("*** Cloning source-code from: %s" % project['url'])
    if os.path.exists('trunk'):
        shutil.rmtree('trunk')
    code = vcs.get_vcs(project['vcs'], project['url'], 'trunk')
    code.clone()
    logging.info("*** Cloning completed")


    # VCS polling
    vcs_info = {'project':project,
                'code':code,
                'source_tree_id':source_tree_id,
                'instance_id':instance_id}
    loop_vcs = PeriodicTask(5 * 60, VcsTask, [conn, vcs_info], name="Check trunk")

    # set revisions to execute integrations from
    # the latest of revision specified on config file or latest executed
    last_revision_id = get_last_revision_id(conn.cursor())
    if last_revision_id >= project['start_rev']:
        loop_vcs.last_rev = last_revision_id
    else:
        loop_vcs.last_rev = project['start_rev']

    # read to start
    sched = Scheduler()
    sched.add_task(loop_vcs)
    sched.loop()
