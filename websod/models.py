from sqlalchemy import Table, Column, ForeignKey
from sqlalchemy import String, Integer, Text, DateTime, Float, Boolean
from sqlalchemy.orm import mapper, relation, backref
from sqlalchemy.sql import functions

from websod.database import metadata


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

integration_result_table = Table(
    'integration_result', metadata,
    Column('id', Integer, primary_key=True),
    Column('integration_id', Integer, ForeignKey('integration.id')),
    Column('new_failures', Text()),
    Column('all_failures', Text()),
    Column('fixed_failures', Text()),
    Column('unstables', Text()),
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
    # do not use DateTime, see: http://groups.google.com/group/sqlalchemy/browse_frm/thread/296129afe60943e5/d035362f3d7dd63b?tvc=1#d035362f3d7dd63b
    Column('started', String()),
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
    # FIXME websod does not handle errors!
    Column('result', String(20)), # success/fail/unstable/error
    Column('log', Text()),
    Column('started', String()),
    Column('elapsed', Float()), # time in seconds
    Column('job_group_id', Integer, ForeignKey('job_group.id')),
    )



######## models  #########

NO_OF_HISTORY_LAST_VALUES = 50


class SourceTreeRoot(object):
    """Reference to a source code repository"""
    def __init__(self, source_location=''):
        self.source_location = source_location


class Integration(object):

    class IntegrationException(Exception): pass
    class NotFinished(IntegrationException): pass
    class AlreadyCalculated(IntegrationException): pass

    def __init__(self, version='', state='', result='',
                 owner='', comment=''):
        self.version = version #TODO rename as "revision" type int
        # FIXME add a column to save integration parent revision
        self.state = state
        self.result = result # FIXME move this to IntegrationResult table
        self.owner = owner
        self.comment = comment

    def __repr__(self):
        return '<Integration (%s)%s - %s:%s>' % (
            self.id, self.version, self.state, self.result)

    # TODO: arghhh. not PEP8
    def getJobs(self):
        if not hasattr(self, 'jobs_list'):
            jobs = []
            for a_jobgroup in self.jobgroups:
                if a_jobgroup:
                    if a_jobgroup.jobs:
                        jobs.extend(a_jobgroup.jobs)
            self.jobs_list = jobs
        return self.jobs_list

    def getJobsByResult(self, result_str):
        return filter(lambda job: job.result == result_str,
                      self.getJobs())

    def getElapsedTime(self):
        total = 0.0
        for jg in self.jobgroups:
            # FIXME there are some unicode values in this column!
            if type(jg.elapsed) is not float:
                continue
            total += jg.elapsed
        return total

    @staticmethod
    def get_elapsed_history(session):
        #the last integrations
        #TODO add limit(NO_OF_HISTORY_LAST_VALUES
        res = session.query(Integration).order_by(Integration.version.desc()).all()

#         #FIXME use SQL to calculate this
#         res = session.query(Integration).filter(Integration.version<self.version).\
#                  order_by(Integration.version.desc()).limit(NO_OF_HISTORY_LAST_VALUES)
#         #calculate the sum of all jobs for every integration
#         sum_array = []
#         for an_integration in res:
#             sum_value = session.query(functions.sum(Job.elapsed)).join(JobGroup).join(Integration).filter(Integration.id==an_integration.id).scalar()
#             print sum_value
#             sum_array.append([int(an_integration.version), sum_value])
#         return sum_array

        result = []
        for rev in res:
            if rev.state != 'finished' or rev.result != 'success':
                continue
            total = rev.getElapsedTime()
            result.append([int(rev.version), total/60.0])
        return result



class IntegrationResult(object):

    def __init__(self, new_failures=None, all_failures=None,
                 fixed_failures=None, unstables=None):
        self.new_failures = new_failures
        self.all_failures = all_failures
        self.fixed_failures = fixed_failures
        self.unstables = unstables

    def __repr__(self):
        return '<IntegrationResult %s>' % (self.integration_id)

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
        # TODO add a "description" column that will hod doit task as in the config.yaml
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

    def get_elapsed_history(self, session):
        #res = session.query(Job).join(JobGroup).join(Integration).filter(Job.name==self.name).filter(Integration.version<self.job_group.integration.version).order_by(Integration.version.desc()).limit(NO_OF_HISTORY_LAST_VALUES)
        # FIXME do not show all integrations
        res = session.query(Job).filter_by(name=self.name).order_by(Job.id)
        return [[int(i.job_group.integration.version), i.elapsed] for i in res if i.elapsed]





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

mapper(IntegrationResult, integration_result_table, properties={
         'integration': relation(Integration, backref=backref('integration_result', uselist=False))})
