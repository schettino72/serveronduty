from werkzeug import redirect
from werkzeug.exceptions import NotFound

from websod.utils import session, expose, url_for, serve_template
from websod.models import Integration, Job

from datetime import timedelta, datetime






@expose('/')
def home(request):
    # show results from last 3 days
    integrations_from = datetime.now() + timedelta(days=-3)
    from_str = integrations_from.strftime("%Y-%m-%d 00:00:00")
    latest_integrations = session.query(Integration).\
        filter("started > '%s'" % from_str).\
        order_by(Integration.started.desc()).all()
    return serve_template('home.html', latest_integrations=latest_integrations)


@expose('/integration/')
def integration_list(request):
    integrations = session.query(Integration).all()
    for integ in integrations:
        if not integ.result:
            integ.calculate_result()
    return serve_template('integration_list.html', integrations=integrations)


@expose('/integration/<int:id>')
def integration(request, id):
    integration = session.query(Integration).get(id)
    return serve_template('integration.html', integration=integration)


