from sqlalchemy.orm import join, outerjoin
from werkzeug import redirect
from werkzeug.exceptions import NotFound

from websod.utils import session, expose, url_for, serve_template
from websod.models import Integration, Job, SourceTreeRoot, JobGroup, IntegrationResult

from datetime import timedelta, datetime

# @expose('/')
# def home(request):
#     # show results from last 3 days
#     integrations_from = datetime.now() + timedelta(days=-3)
#     from_str = integrations_from.strftime("%Y-%m-%d 00:00:00")
#     latest_integrations = session.query(Integration).\
#         filter("started > '%s'" % from_str).\
#         order_by(Integration.started.desc()).all()
#     return serve_template('home.html')


@expose('/') #TODO show only latest integrations. see home function above
@expose('/integration/')
def integration_list(request):
    integrations = session.query(Integration).order_by(Integration.id.desc()).all()
    _massage_integrations(integrations)
    return serve_template('integration_list.html', integrations=integrations,
                          history=Integration.get_elapsed_history())

def _massage_integrations(integrations):
    for i, intg in enumerate(integrations[:-1]):
        if intg.state != 'finished':
            intg.unstables = intg.getJobsByResult("unstable")
            intg.failures = intg.getJobsByResult('fail')
            intg.fixed_failures = []

        if getattr(intg, 'integration_result', None):
            new_failure_ids = intg.integration_result.new_failures.split(',')
            fix_failure_ids = intg.integration_result.fixed_failures.split(',')
            unstable_ids = intg.integration_result.unstables.split(',')
            failure_ids = intg.integration_result.all_failures.split(',')

            new_failure_ids = [] if new_failure_ids == [''] else map(int, new_failure_ids)
            fix_failure_ids = [] if fix_failure_ids == [''] else map(int, fix_failure_ids)
            unstable_ids = [] if unstable_ids == [''] else map(int, unstable_ids)
            failure_ids = [] if failure_ids == [''] else map(int, failure_ids)

        else:
            unstables = intg.getJobsByResult("unstable")
            failures = intg.getJobsByResult('fail')
            new_failure_ids, fix_failure_ids = _compare_integrations(failures, integrations[i+1].getJobsByResult('fail'))

            failure_ids = [failure.id for failure in failures]
            unstable_ids = [unstable.id for unstable in unstables]
            intg.integration_result = IntegrationResult(new_failures=','.join(map(str, new_failure_ids)),
                                                        all_failures=','.join(map(str, failure_ids)),
                                                        fixed_failures=','.join(map(str, fix_failure_ids)),
                                                        unstables=','.join(map(str, unstable_ids)))

        intg.failures = [_get_job_instance(failure_id)
                         for failure_id in failure_ids]
        intg.unstables = [_get_job_instance(_id)
                         for _id in unstable_ids]
        intg.fixed_failures = [_get_job_instance(failure_id)
                               for failure_id in fix_failure_ids]

        for failure in intg.failures:
            if failure.id in new_failure_ids:
                failure.new_failure = True

    session.commit()

    intg = integrations[-1]
    intg.unstables = intg.getJobsByResult("unstable")
    intg.failures = intg.getJobsByResult('fail')
    intg.fixed_failures = []

def _compare_integrations(new_integ_jobs, old_integ_jobs):
    # job.log is not included in comparsion since the error log contain
    # file path which is different between revisions.
    _get_job_info = lambda job: (job.name, job.type, job.result, job.state)

    new_come_jobs = {}
    old_jobs = {}
    for job in old_integ_jobs:
        old_jobs[_get_job_info(job)] = job.id

    for job in new_integ_jobs:
        job_info = _get_job_info(job)
        if job_info in old_jobs:
            old_jobs.pop(job_info)
        else:
            new_come_jobs[job_info] = job.id

    # return ids only
    return new_come_jobs.values(), old_jobs.values()

def _get_job_instance(job_id, job_list=None):
    if job_list:
        for job in job_list:
            if job_id == job.id:
                return job
    return session.query(Job).get(job_id)

@expose('/integration/<int:id>')
def integration(request, id):

    # use lazy loading of referenced object to SQLAlchemy to handle everything
    integration = session.query(Integration).get(id)
    # collect the failed jobs
    failed_jobs = integration.getJobsByResult("fail")
    unstable_jobs = integration.getJobsByResult("unstable")
    success_jobs = integration.getJobsByResult("success")

    return serve_template('integration.html', integration=integration,
            failed_jobs=sorted(failed_jobs, key=lambda k: k.name),
            unstable_jobs=sorted(unstable_jobs, key=lambda k: k.name),
            success_jobs=sorted(success_jobs, key=lambda k: k.name),
                          )



@expose('/job/<int:id>')
def job(request, id):
    the_job = session.query(Job).get(id)
    elapsed_history = the_job.get_elapsed_history()
    return serve_template('job.html', job=the_job, history=elapsed_history)




@expose('/testdata')
def add_testdata(request):

    print request.method
    # do not support non-POST requests
    if request.method != 'POST':
        # TODO: maybe forward to an error page
        raise NotFound()

    sourceRoot = SourceTreeRoot('/trunk')

    # a set of jobs to add to groups

    job1 = Job("/test/file1.py", "unit", "success", 'log',
               None, None,'finished')
    job2 = Job("/ftest/ftest_file1.py", "ftest", "success", 'log',
               None, None,'finished')
    job3 = Job("/test/file2.py", "unit", "fail", 'log',
               None, None,'finished')
    job4 = Job("/test/file3.py", "ftest", "unstable", 'log',
               None, None,'finished')
    # this will link different job groups to the same job object, but it is not
    # a problem for now

    jobgroup_i1_1 = JobGroup(None, None, 'finished', 'success', 'log')
    jobgroup_i1_1.jobs = [job1, job2]
    jobgroup_i1_2 = JobGroup(None, None, 'finish', 'failed', 'log')
    i1 = Integration('20898','finished','fail', 'balazs', 'test comment')
    jobgroup_i1_2.jobs = [job1, job3, job4]
    i1.source_tree_root = sourceRoot
    i1.jobgroups = [jobgroup_i1_1, jobgroup_i1_2]

    jobgroup_i2_1 = JobGroup(None, None, 'finished', 'fail', 'log')
    jobgroup_i2_1.jobs = [job4]
    jobgroup_i2_2 = JobGroup(None, None, 'finished', 'fail', 'log')
    jobgroup_i2_1.jobs = [job4]
    i2 = Integration('20899','finished','success', 'eduardo', 'tc2')
    i2.source_tree_root = sourceRoot
    i2.jobgroups = [jobgroup_i2_1, jobgroup_i2_2]
    session.add_all([i1,i2])
    session.commit()
    # after commit, the ID's are updated for inserted objects

    # go to the integration list page
    return redirect('/integration')
