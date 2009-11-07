from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy import String, Integer, Text, DateTime, Float
from sqlalchemy.orm import mapper, relation
from websod.utils import metadata, session



integration_table = Table(
    'integration', metadata,
    Column('id', Integer, primary_key=True),
    Column('source', String(40)), # repository location
    Column('revision', String(20)), # VCS revision number
    Column('machine', String(40)), # where it was executed
    Column('result', String(20)),
    Column('log', Text()), # if no tests can be executed, a log is generated about it
    Column('started', DateTime()),
    Column('elapsed', Float()), # time in seconds
    Column('committer', String(40)), # the person who created this revision
    Column('comment', String(1024)), # the commit comment for the revision, length should be considered
    )


job_table = Table(
    'job', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(100)),
    Column('type', String(20)),
    Column('integration_id', Integer, ForeignKey('integration.id')),
    Column('result', String(20)),
    Column('log', Text()),
    Column('started', DateTime()),
    Column('elapsed', Float()), # time in seconds
    )


class Integration(object):
    def __init__(self, source='', revision='', machine='', result='',
                 log='', started=None ,elapsed=None, committer='', comment=''):
        self.source = source
        self.revision = revision
        self.machine = machine
        self.result = result
        self.log = log
        self.started = started
        self.elapsed = elapsed
        self.committer = committer
        self.comment = comment

    def __repr__(self):
        return '<Integration (%s)%s - %s:%s>' % (
            self.id, self.machine, self.source, self.revision)

    def calculate_result(self):
        result = "success" # optimistic
        non_success = session.query(Job).filter(Job.integration_id==self.id).\
            filter(Job.result!="success")
        for job in non_success:
            # check if any of the entries for this job was successful
            job_results = session.query(Job).filter(Job.integration_id==self.id).\
                filter(Job.name==job.name).filter(Job.result=='success').all()
            if job_results:
                result = 'unstable'
            else:
                result = 'error'
                break
        self.result = result


class Job(object):
    def __init__(self, name, type='', result='', log='',
                 started=None, elapsed=None):
        self.name = name
        self.type = type
        self.result = result
        self.log = log
        self.started = started
        self.elapsed = elapsed

    def __repr__(self):
        return '<Job %s>' % self.name


mapper(Integration, integration_table)
mapper(Job, job_table, properties={
        'integration': relation(Integration, backref='jobs')
        })
