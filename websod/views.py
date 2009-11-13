from werkzeug import redirect
from werkzeug.exceptions import NotFound

from websod.utils import session, expose, url_for, serve_template
from websod.models import Integration, Job

from datetime import timedelta, datetime

def home(request):
    # show results from last 3 days
    integrations_from = datetime.now() + timedelta(days=-3)
    from_str = integrations_from.strftime("%Y-%m-%d 00:00:00")
    latest_integrations = session.query(Integration).\
        filter("started > '%s'" % from_str).\
        order_by(Integration.started.desc()).all()
    return serve_template('home.html', latest_integrations=latest_integrations)


@expose('/integration/<int:id>')
def integration(request, id):
    integration = session.query(Integration).get(id)
    tests = {}
    jobs = session.query(Job).filter(Job.integration_id==id).\
        order_by(Job.name)
    for jb in jobs:
        if jb.name not in tests:
            tests[jb.name] = jb
            continue
        if jb.result != tests[jb.name].result:
            if jb.result == 'fail':
                tests[jb.name] = jb #display the fail log for unstable ones
            tests[jb.name].result = 'unstable'
    return serve_template('integration.html', integration=integration,
                          jobs=sorted(tests.values(), key=lambda k: k.name))


@expose('/')
@expose('/integration/')
def integration_list(request):
    integrations = session.query(Integration).order_by(Integration.started.desc()).all()
    for integ in integrations:
# this might give a wrong result if page is viewed before the tests finishes running
#        if not integ.result:
        integ.calculate_result()

    return serve_template('integration_list.html', integrations=integrations)

@expose('/job/<int:id>')
def job(request, id):
    the_job = session.query(Job).get(id)
    return serve_template('job.html', job=the_job)

