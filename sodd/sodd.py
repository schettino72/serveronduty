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


import vcs

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


def loop_vcs(code, start_from, integrate_list, new_event):
    last_rev = start_from
    while True:
        revs = code.get_new_revisions(last_rev)
        print "got revs: %s" % ", ".join(revs)

        if(revs):
            integrate_list.extend(revs)
            new_event.set()
            last_rev = integrate_list[-1]
        #time.sleep(10*60)
        time.sleep(20)


def main(project):

    conn = sqlite3.connect("../sod.db")
    base_path = os.path.abspath(__file__ + '/../pool/')

    # list of integrations to be processed
    integrate_list = []

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

        integrate_rev = integrate_list.pop(0)
        print "starting integration %s" % integrate_rev

        # export revision to be tested
        integration_path = base_path + '/' + integrate_rev
        code.export(integrate_rev, integration_path)
        # FIXME NBET stuff
        # shutil.copy(base_path + "/dodo.py", integration_path + "/dodo.py")
        # shutil.copy(integration_path + '/local_config.py.DEVELOPER',
        #             integration_path + '/local_config.py')

        integration_id = save_integration(conn.cursor(), project['url'],
                                          integrate_rev, 'kevin')

        for task in project['tasks']:
            json_result = doit_unstable_integration(integration_path, task)
            #result = simplejson.loads(json_result)
            save_job(conn.cursor(), json_result, integration_id, task)
            conn.commit()
        print "finished integration %s" % integrate_rev


if __name__ == "__main__":
    import sys
    if len(sys.argv)!= 2:
        print "usage: python sodd.py <project.json>"
    project_file = open(sys.argv[1])
    project = simplejson.load(project_file)
    main(project)


