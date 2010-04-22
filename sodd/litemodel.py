"""DB operation using SQLite"""

from dbapiext import execute_f

# FIXME this code is so boring...


def get_last_id(cursor):
    # sqlite
    if cursor.lastrowid:
        return cursor.lastrowid
    # postgres/psycopg2 do not set lastrowid!
    cursor.execute('select lastval();')
    return cursor.fetchone()[0]

#
# integration
#
def save_integration(cursor, version, state, result, owner, comment,
                     source_tree_root_id):
    execute_f(cursor, '''
        INSERT INTO integration (version, state, result, owner, comment,
                          source_tree_root_id) VALUES (%X,%X,%X,%X,%X,%X)''',
              version, state, result, owner, comment, source_tree_root_id)
    cursor.connection.commit()
    return get_last_id(cursor)


def get_last_revision_id(cursor):
    cursor.execute('''
        SELECT version FROM integration order by version desc''')
    res = cursor.fetchone()
    if res:
        return int(res[0])
    else:
        # if integration table have no rows, return 0 as default
        return 0


#
# source_tree_root
#
def save_source_tree_root(cursor, source_location):
    execute_f(cursor, '''
        INSERT INTO source_tree_root (source_location) VALUES (%X)''',
              source_location)
    cursor.connection.commit()
    return get_last_id(cursor)


#
# sodd_instance
#
def save_sodd_instance(cursor, name, machine):
    execute_f(cursor, '''
        INSERT INTO sodd_instance (name, machine) VALUES (%X,%X)''',
              name, machine)
    cursor.connection.commit()
    return get_last_id(cursor)

#
# job_group
#
def db_job_group_start(cursor, started, elapsed, state, result, log,
                       integration_id, sodd_instance_id):
    execute_f(cursor, '''
        INSERT INTO job_group (started, elapsed, state, result,
                     log, integration_id, sodd_instance_id) VALUES
                     (%X,%X,%X,%X,%X,%X,%X)''',
                   started, elapsed, state, result, log, integration_id,
                   sodd_instance_id)
    cursor.connection.commit()
    return get_last_id(cursor)

def db_job_group_finish(cursor, id_, elapsed, result, log, state='finished'):
    execute_f(cursor, '''
        UPDATE job_group SET elapsed=%X, state=%X, result=%X, log=%X WHERE
                        id=%X''', elapsed, state, result, log, id_)
    cursor.connection.commit()


#
# job
#
def save_job(cursor, result, type_, id_):
    for row in result:
        execute_f(cursor, '''
            INSERT INTO job (name, type, state, result, log, started, elapsed,
                             job_group_id)
            VALUES (%X,%X,%X,%X,%X,%X,%X,%X)''',
                       row['name'], type_, 'finished', row['result'],
                       row['err']+row['out'],row['started'],row['elapsed'], id_)
    cursor.connection.commit()
