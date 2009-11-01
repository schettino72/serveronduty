from werkzeug import redirect
from werkzeug.exceptions import NotFound

from websod.utils import session, expose, url_for, serve_template
from websod.models import Integration

from datetime import timedelta, datetime

@expose('/')
def home(request):
    #integrations = session.query(Integration).all()

    #currently this is just an assumption, that 3 days will be OK
    integrations_from = datetime.now() + timedelta(days=-3)
    from_str = integrations_from.strftime("%Y-%m-%d 00:00:00")
    last_integrations = session.query(Integration).filter("started > '"+from_str+"'").all()
    return serve_template('home.html', last_integrations = last_integrations)

@expose('/integration/<int:id>')
def integration(request, id):
    integration = session.query(Integration).get(id)
    return serve_template('integration.html', integration=integration)

@expose('/integration/')
def integration_list(request):
    integrations = session.query(Integration).all()
    return serve_template('integration_list.html', integrations=integrations)
