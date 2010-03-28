from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy import String, Integer, Text, DateTime, Float, Boolean
from sqlalchemy.orm import mapper, relation
from websod.utils import metadata, session

source_tree_root_table = Table(
    'source_tree_root', metadata,
    Column('id', Integer, primary_key=True),
    Column('source_location', String(60)), # repository location
    )

integration_table = Table(
    'integration', metadata,
    Column('id', Integer, primary_key=True),
    # VCS revision number or working copy identifier
    Column('version', String(20)),
    # running/waiting/finished
    Column('state', String(10)),
    Column('result', String(20)),
    # the person who created this revision or working copy owner
    Column('owner', String(40)),
    # the commit comment for the revision, length should be considered
    Column('comment', String(1024)),
    Column('source_tree_root_id', Integer, ForeignKey('source_tree_root.id')),
    )

sodd_instance_table = Table(
    'sodd_instance', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(30)),
    Column('machine', String(40)), # where it was executed
    )

job_group_table = Table(
    'job_group', metadata,
    Column('id', Integer, primary_key=True),
    Column('started', DateTime()),
    Column('elapsed', Float()), # time in seconds
    Column('state', String(10)), # running/waiting/finished
    Column('result', String(10)),
    # if no tests can be executed, a log is generated about it
    Column('log', Text()),
    Column('integration_id', Integer, ForeignKey('integration.id')),
    Column('sodd_instance_id', Integer, ForeignKey('sodd_instance.id')),
    )

job_table = Table(
    'job', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(100)),
    Column('type', String(20)),
    Column('state', String(10)), # running/waiting/finished
    Column('result', String(20)),
    Column('log', Text()),
    Column('started', DateTime()),
    Column('elapsed', Float()), # time in seconds
    # calculated field, the job can be added, same or removed
    # in this version/revision
    Column('create_status', String(10)),
    Column('introduced_result', Boolean()),
    # calculated field, the job result is new (true) or same (false)
    # compared to the last version/revision
    Column('job_group_id', Integer, ForeignKey('job_group.id')),
    )



######## models  #########


class SourceTreeRoot(object):
    """Reference to a source code repository"""
    def __init__(self, source_location=''):
        self.source_location = source_location


class Integration(object):

    def __init__(self, version='', state='', result='',
                 owner='', comment=''):
        self.version = version
        self.state = state
        self.result = result
        self.owner = owner
        self.comment = comment

    def __repr__(self):
        return '<Integration (%s)%s - %s:%s>' % (
            self.id, self.version, self.state, self.result)

    def getJobsByResult(self, result_str):
        retlist = []
        for a_jobgroup in self.jobgroups:
            retlist.extend(
                [a_job for a_job in a_jobgroup.jobs
                            if a_job.result == result_str])

        return retlist


class SoddInstance(object):
    """A machine/configuration where the integration is executed"""
    def __init__(self, name='', machine=''):
        self.name = name
        self.machine = machine

    def __repr__(self):
        return '<SoddInstance %s (%s)>' % (self.name, self.machine)


class JobGroup(object):
    """A group of jobs executed on the same SoddInstance"""
    def __init__(self, started=None, elapsed=None, state='', result='', log='', ):
        self.started = started
        self.elapsed = elapsed
        self.state = state
        self.result = result
        self.log = log

    def __repr__(self):
        return '<JobGroup %s (%s,%s)>' % (self.id, self.state, self.result)


class Job(object):
    def __init__(self, name, type='', result='', log='',
                 started=None, elapsed=None, state=''):
        self.name = name
        self.type = type
        self.result = result
        self.log = log
        self.started = started
        self.elapsed = elapsed
        self.state = state

    def __repr__(self):
        return '<Job %s>' % self.name

    def get_elapsed_history(self):
        res = session.query(Job).filter_by(name=self.name).order_by(Job.id)[:50]
        return [[int(i.job_group.integration.version), i.elapsed] for i in res]

mapper(SourceTreeRoot, source_tree_root_table)

mapper(SoddInstance, sodd_instance_table)

mapper(Integration, integration_table, properties={
        'source_tree_root': relation(SourceTreeRoot, backref='integrations')
        })

mapper(JobGroup, job_group_table, properties={
        'integration': relation(Integration, backref='jobgroups'),
        'sodd_instance': relation(SoddInstance, backref='jobgroups')
        })

mapper(Job, job_table, properties={
        'job_group': relation(JobGroup, backref='jobs')
        })
