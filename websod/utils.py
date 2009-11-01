from os import path

from werkzeug import Local, LocalManager
from werkzeug import Response
from werkzeug.routing import Map, Rule

from sqlalchemy import MetaData
from sqlalchemy.orm import create_session, scoped_session

from mako.lookup import TemplateLookup
from mako import exceptions


############ werkzeug
local = Local()
local_manager = LocalManager([local])
application = local('application')


############ SQLAlchemy
metadata = MetaData()
session = scoped_session(lambda: create_session(application.database_engine,
                         autocommit=False), local_manager.get_ident)



############## mako
# calculate the path of the folder this file is in, the application will
# look for templates in that path
root_path = path.abspath(path.dirname(__file__))

# create a mako template loader for that folder and set the default input
# encoding to utf-8
template_lookup = TemplateLookup(directories=[path.join(root_path, 'templates')],
                                 input_encoding='utf-8')


def serve_template(templatename, **kwargs):
    try:
        mytemplate = template_lookup.get_template(templatename)
        kwargs['url_for'] = url_for
        return Response(mytemplate.render(**kwargs),
                        mimetype='text/html')
    except:
        return Response(exceptions.html_error_template().render(),
                        mimetype='text/html')


############# URL mapping
# check new support for static files.
url_map = Map([Rule('/static/<file>', endpoint='static', build_only=True)])
def expose(rule, **kw):
    def decorate(f):
        kw['endpoint'] = f.__name__
        url_map.add(Rule(rule, **kw))
        return f
    return decorate

def url_for(endpoint, _external=False, **values):
    return local.url_adapter.build(endpoint, values, force_external=_external)

