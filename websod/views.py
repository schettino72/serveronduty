from sqlalchemy.orm import join, outerjoin
from werkzeug import redirect
from werkzeug.exceptions import NotFound

from websod.utils import session, expose, url_for, serve_template
from websod.models import Integration, Job, SourceTreeRoot, JobGroup

from datetime import timedelta, datetime

def home(request):
    # show results from last 3 days
#    integrations_from = datetime.now() + timedelta(days=-3)
#    from_str = integrations_from.strftime("%Y-%m-%d 00:00:00")
#    latest_integrations = session.query(Integration).\
#        filter("started > '%s'" % from_str).\
#        order_by(Integration.started.desc()).all()
    return serve_template('home.html')


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
            success_jobs=sorted(success_jobs, key=lambda k: k.name))

@expose('/')
@expose('/integration/')
def integration_list(request):
    integrations = session.query(Integration).order_by(Integration.id.desc()).all()
    #for integ in integrations:
# this might give a wrong result if page is viewed before the tests finishes running
#        if not integ.result:
    #    integ.calculate_result()

    return serve_template('integration_list.html', integrations=integrations)

@expose('/job/<int:id>')
def job(request, id):
    the_job = session.query(Job).get(id)
    return serve_template('job.html', job=the_job)

@expose('/testdata')
def add_testdata(request):

    print request.method
    # do not support non-POST requests
    if request.method != 'POST':
        # TODO: maybe forward to an error page
        raise NotFound()

    sourceRoot = SourceTreeRoot('/trunk')

    # a set of jobs to add to groups

    job1 = Job("/test/file1.py", "unit", "success", 'log', None, None,'finished')
    job2 = Job("/ftest/ftest_file1.py", "ftest", "success", 'log', None, None,'finished')
    job3 = Job("/test/file2.py", "unit", "fail", 'log', None, None,'finished')
    job4 = Job("/test/file3.py", "ftest", "unstable", 'log', None, None,'finished')
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
