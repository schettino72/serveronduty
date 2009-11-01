from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy import String, Integer, Text, DateTime, Interval
from sqlalchemy.orm import mapper, relation
from websod.utils import metadata



integration_table = Table(
    'integration', metadata,
    Column('id', Integer, primary_key=True),
    Column('source', String(40)), # repository location
    Column('revision', String(20)), # VCS revision number
    Column('machine', String(40)), # where it was executed
    Column('result', String(20)),
    Column('log', Text()), # if no tests can be executed, a log is generated about it
    Column('started', DateTime()),
    Column('elapsed', Interval()),
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
    Column('elapsed', Interval()),
    )


class Integration(object):
    def __init__(self, source='', revision='', machine='', result='',
                 log='', started=None ,elapsed=None):
        self.source = source
        self.revision = revision
        self.machine = machine
        self.result = result
        self.log = log
        self.started = started
        self.elapsed = elapsed

    def __repr__(self):
        return '<Integration (%s)%s - %s:%s>' % (
            self.id, self.machine, self.source, self.revision)



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
