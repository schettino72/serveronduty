"""DB operation using SQLite"""
# FIXME this code is so boring... is there a lightweight single-file ORM?


#
# integration
#
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


#
# source_tree_root
#
def save_source_tree_root(cursor, source_location):
    cursor.execute('''
        INSERT INTO source_tree_root (source_location) VALUES (?)''',
        (source_location,))
    cursor.connection.commit()
    return cursor.lastrowid


#
# sodd_instance
#
def save_sodd_instance(cursor, name, machine):
    cursor.execute('''
        INSERT INTO sodd_instance (name, machine) VALUES (?,?)''',
        (name, machine))
    cursor.connection.commit()
    return cursor.lastrowid

#
# job_group
#
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


#
# job
#
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