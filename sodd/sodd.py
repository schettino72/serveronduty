import os
import shutil
import subprocess
import threading
import time
import datetime

import simplejson
import yaml

try:
    import sqlite3
except ImportError:
    from pysqlite2 import dbapi2 as sqlite3


import vcs

def doit_unstable_integration(base_path, task_name):
    """wrap doit integration with some logic to deal with unstable tests

    every task in doit will be mapped to one job
    """
    dodo = '%s/dodo.py' % base_path
    run_cmd = ['doit', '-f', dodo, '--reporter', 'json',
               '--output-file', '%s/result.json' % base_path, task_name]
    ignore_cmd = "doit -f %s ignore %s"

    # key: task/job name
    # value: list of results (dict)
    FINAL_RESULT = {}
    while True:
        if os.path.exists('%s/result.json' % base_path):
            os.remove('%s/result.json' % base_path)
        print "doit integration in %s" % base_path
        run_p = subprocess.Popen(run_cmd, stdout=subprocess.PIPE)
        run_p.communicate()
        result_file = open('%s/result.json' % base_path,'r')
        output = result_file.read()
        result_file.close()
        try:
            try_results = simplejson.loads(output)
        except ValueError, ve:
            print "JSON loading failed: " + output
            raise

        added_something = False
        for res in try_results['tasks']:
            print "============>", res['name'], " +++> ", res['result']
            if res['result'] in ('up-to-date', 'ignore'):
                continue
            added_something = True

            if res['name'] not in FINAL_RESULT:
                # execute first time. just add it to the list
                FINAL_RESULT[res['name']] = res
            else:
                # if it fails on previous run
                if FINAL_RESULT[res['name']]['result'] == 'fail':
                    # task failed again. real failure, ignore it on next run
                    if res['result'] == 'fail':
                        cmd = (ignore_cmd % (dodo, res['name'])).split()
                        subprocess.Popen(cmd).communicate()
                    # fail on previous run but passed now, mark as unstable.
                    # keep output from failure
                    else:
                        FINAL_RESULT[res['name']]['result'] = 'unstable'
                else:
                    # for tasks that are repeated even when successful,
                    # save them only case of failure
                    if res['result'] == 'fail':
                        FINAL_RESULT[res['name']] = res


        # exit from loop
        # successful returncode will be zero when all tasks have been run
        # added_something is necessary to get errors that unable tasks to run
        if (run_p.returncode == 0) or (not added_something):
            break

    return FINAL_RESULT.itervalues()



def doit_forget(base_path):
    # make sure we have a clean run
    forget_cmd = "doit -f %s/dodo.py forget"
    subprocess.Popen((forget_cmd % base_path).split()).communicate()


def save_integration(cursor, version, state, result, owner, comment,
                                                                source_tree_root_id):
    cursor.execute('''
        INSERT INTO integration (version, state, result, owner, comment,
                                source_tree_root_id) VALUES (?,?,?,?,?,?)''',
                        (version, state, result, owner, comment, source_tree_root_id))
    cursor.connection.commit()
    return cursor.lastrowid

def update_integration(cursor, id_, result, state='finished'):
    cursor.execute('''UPDATE integration SET state=?, result=? WHERE id=?''',
                   (state, result, id_))
    cursor.connection.commit()

def save_source_tree_root(cursor, source_location):
    cursor.execute('''
        INSERT INTO source_tree_root (source_location) VALUES (?)''',
        (source_location,))
    cursor.connection.commit()
    return cursor.lastrowid

def save_sodd_instance(cursor, name, machine):
    cursor.execute('''
        INSERT INTO sodd_instance (name, machine) VALUES (?,?)''',
        (name, machine))
    cursor.connection.commit()
    return cursor.lastrowid

def save_job_group(cursor, started, elapsed, state, result, log, integration_id,
                                                                sodd_instance_id):
    cursor.execute('''
        INSERT INTO job_group (started, elapsed, state, result,
                     log, integration_id, sodd_instance_id) VALUES
                     (?,?,?,?,?,?,?)''',
        (started, elapsed, state, result, log, integration_id,
                                                            sodd_instance_id))
    cursor.connection.commit()
    return cursor.lastrowid

def update_job_group(cursor, id_, elapsed, result, log, state='finished'):
    cursor.execute('''
        UPDATE job_group SET elapsed=?, state=?, result=?, log=? WHERE
                        id=?''', (elapsed, state, result, log, id_))
    cursor.connection.commit()

def save_job(cursor, result, type_, id_):
    for row in result:
        cursor.execute('''
            INSERT INTO job (name, type, state, result, log, started, elapsed,
                            create_status, introduced_result, job_group_id)
            VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (row['name'], type_, 'finished', row['result'],
             row['err']+row['out'],row['started'],row['elapsed'],
             # I think create_status and introduced_result should be got from
             # the output of DOIT. Here just set a default value for them
             # temporarily
             'create_status', True, id_))
    cursor.connection.commit()

def loop_vcs(code, start_from, integrate_list, new_event):
    last_rev = start_from
    while True:
        revs = code.get_new_revisions(last_rev)
        for a_rev in revs:
            print "got rev: %s" % a_rev['revision']

        if(revs):
            integrate_list.extend(revs)
            new_event.set()
            last_rev = integrate_list[-1]['revision']
        #time.sleep(10*60)
        time.sleep(60)


def main(project_file):
    project = yaml.load(open(project_file))
    conn = sqlite3.connect("../sod.db")

    ## register self in sodd_instance table
    ## TODO seems need a rule to name sodd and machine
    instance_id = save_sodd_instance(conn.cursor(), 'SODD 1', 'qtest')

    #TODO: maybe it would be good to have a configuration entry for this
    base_path = os.path.abspath(__file__ + '/../pool/')

    #if pool is an existing file, that is an error
    if os.path.isfile(base_path):
        raise Exception("pool exists and is a file")
    #if the directory does not exist create it
    if not os.path.isdir(base_path):
        os.mkdir(base_path)

    # list of integrations to be processed
    integrate_list = []

    # insert into source_location table
    source_tree_id = save_source_tree_root(conn.cursor(), project['url'])

    if os.path.exists('trunk'):
        shutil.rmtree('trunk')
    code = vcs.get_vcs(project['vcs'], project['url'], 'trunk')
    code.clone()

    # create thread for VCS polling
    newIntegration = threading.Event()
    newIntegration.set()
    args = (code, project['start_rev'], integrate_list, newIntegration)
    looping_vcs_t = threading.Thread(target=loop_vcs, args=args)
    # FIXME use event to kill thread (daemon threads is known to be unreliable)
    looping_vcs_t.daemon = True
    looping_vcs_t.start()

    # execute integration tasks
    while True:
        # block until we get some work
        if not integrate_list:
            newIntegration.clear()
            # thread locking can't get Keyboard interrupts while blocked
            while not newIntegration.isSet():
                newIntegration.wait(1)

        #integrate rev is a dictionary to describe the revision
        integrate_rev = integrate_list.pop(0)
        print "starting integration %s" % integrate_rev['revision']
        integration_id = save_integration(
            conn.cursor(), integrate_rev['revision'], 'running', 'unknown',
            integrate_rev['committer'], integrate_rev['comment'],
            source_tree_id)

        started_on = time.time()
        started = datetime.datetime.utcfromtimestamp(started_on)

        # export revision to be tested
        integration_path = base_path + '/' + integrate_rev['revision']
        code.archive(integrate_rev['revision'], integration_path)
        # FIXME NBET stuff
        shutil.copy(base_path + "/dodo.py", integration_path + "/dodo.py")
        shutil.copy(integration_path + '/local_config.py.DEVELOPER',
                     integration_path + '/local_config.py')


        integration_result = 'success'
        for task in project['tasks']:
            print "starting task: ", task
            group_result = 'success'
            group_id = save_job_group(conn.cursor(), started, 'unknown',
                        'running', 'unknown', '', integration_id, instance_id)
            json_result = doit_unstable_integration(integration_path, task)
            #result = simplejson.loads(json_result)
            save_job(conn.cursor(), json_result, task, group_id)

            # check result of this job group
            for each in json_result:
                if each['result'] != 'success':
                    group_result = 'fail'
                    integration_result = 'fail'
                    break

            elapsed = time.time() - started_on
            update_job_group(conn.cursor(), group_id, elapsed, group_result, '')

        print "finished integration %s" % integrate_rev
        update_integration(conn.cursor(), integration_id, '???')

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print 'usage: python sodd.py <project.yaml>'
    proj_file = sys.argv[1]
    main(proj_file)
