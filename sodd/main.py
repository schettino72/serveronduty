import subprocess
import simplejson
import threading
import os
import time
import shutil

try:
    import sqlite3
except ImportError:
    from pysqlite2 import dbapi2 as sqlite3


import vcstool

def doit_unstable_integration(base_path, task_name):
    """wrap doit integration with some logic to deal with unstable tests

    every task in doit will be mapped to one job
    """
    dodo = '%s/dodo.py' % base_path
    run_cmd = "doit -f %s -r json %s"
    ignore_cmd = "doit -f %s ignore %s"

    # key: task/job name
    # value: list of results (dict)
    FINAL_RESULT = {}
    while True:
        run_p = subprocess.Popen((run_cmd % (dodo, task_name)).split(),
                                 stdout=subprocess.PIPE)
        output = run_p.communicate()[0]
        print "&&&&" * 20
        print output
        print "&&&&" * 20
        try_results = simplejson.loads(output)
        added_something = False
        for res in try_results:
            if res['result'] in ('up-to-date', 'ignore'):
                continue
            added_something = True
            # task failed again. real failure, ignore it on next run
            if res['name'] in FINAL_RESULT:
                assert FINAL_RESULT[res['name']][0]['result'] == 'fail', FINAL_RESULT
                subprocess.Popen((ignore_cmd % (dodo, res['name'])).split()).communicate()
                FINAL_RESULT[res['name']].append(res)
            else:
                FINAL_RESULT[res['name']] = [res]

        # exit from loop
        # successful returncode will be zero when all tasks have been run
        # added_something is necessary to get errors that unable tasks to run
        if (run_p.returncode == 0) or (not added_something):
            break
    results = []
    for res in FINAL_RESULT.itervalues():
        results.extend(res)
    return results


def doit_forget(base_path):
    # make sure we have a clean run
    forget_cmd = "doit -f %s/dodo.py forget"
    subprocess.Popen((forget_cmd % base_path).split()).communicate()

def save_integration(cursor, source, revision, machine):
    cursor.execute('''INSERT INTO integration (source, revision, machine)
                                    VALUES (?, ?, ?)''',
                                    (source, revision, machine))
    cursor.connection.commit()
    return cursor.lastrowid

def save_job(cursor, result, type_, integration_id):
    for row in result:
        cursor.execute('''INSERT INTO job (name, integration_id, type, result, log, started, elapsed)
            VALUES (?,?,?,?,?,?,?)''',
            (row['name'], integration_id, type_,
            row['result'],row['err']+row['out'],row['started'],row['elapsed']))
    cursor.connection.commit()


def loop_vcs(vcs, start_from, integrate_list, new_event):
    last_rev = start_from
    while True:
        revs = vcs.getRevisionNumbers(last_rev)

        if(revs):
            integrate_list.extend(revs)
            new_event.set()
            last_rev = integrate_list[-1]
        time.sleep(10*60)


def main(project):

    conn = sqlite3.connect("../sod.db")
    base_path = os.path.abspath(__file__ + '/../pool/')

    # list of integrations to be processed
    integrate_list = []

    vcs = vcstool.VcsTool(project['url'])
    vcs.makeWorkingCopy('trunk')

    # create thread for VCS polling
    newIntegrationAvailable = threading.Event()
    newIntegrationAvailable.set()
    args = (vcs, project['start_rev'], integrate_list, newIntegrationAvailable)
    looping_vcs_t = threading.Thread(target=loop_vcs, args=args)
    # FIXME use event to kill thread (daemon threads is known to be unreliable)
    looping_vcs_t.daemon = True
    looping_vcs_t.start()

    # execute integration tasks
    while True:
        # block until we get some work
        if not integrate_list:
            newIntegrationAvailable.clear()
            newIntegrationAvailable.wait()

        integrate_rev = integrate_list.pop(0)
        integration_path = base_path + '/' + integrate_rev
        vcs.export(integrate_rev, integration_path)
        shutil.copy(base_path + "/dodo.py", integration_path + "/dodo.py")
        shutil.copy(integration_path + '/local_config.py.DEVELOPER',
                    integration_path + '/local_config.py')

        for task in project['tasks']:
            json_result = doit_unstable_integration(integration_path, task)
            #result = simplejson.loads(json_result)
            integration_id = save_integration(conn.cursor(), project['url'],
                                              integrate_rev, 'kevin')
            save_job(conn.cursor(), json_result, integration_id, task)
            conn.commit()


if __name__ == "__main__":
    from project import NBET
    main(NBET)
