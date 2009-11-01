from os import path
from sqlalchemy import create_engine
from werkzeug import SharedDataMiddleware
from werkzeug import Request, ClosingIterator
from werkzeug.exceptions import HTTPException

from websod.utils import session, metadata
from websod.utils import local, local_manager
from websod.utils import url_map
from websod import views
import websod.models
websod # keeps pyflakes quiet


STATIC_PATH = path.join(path.dirname(__file__), 'static')

class WebSod(object):

    def __init__(self, db_uri):
        local.application = self
        self.database_engine = create_engine(db_uri, convert_unicode=True)
        self.dispatch = SharedDataMiddleware(self.dispatch, {
                '/static':  STATIC_PATH
                })


    def init_database(self):
        metadata.create_all(self.database_engine)

    def dispatch(self, environ, start_response):
        local.application = self
        request = Request(environ)
        local.url_adapter = adapter = url_map.bind_to_environ(environ)
        try:
            endpoint, values = adapter.match()
            handler = getattr(views, endpoint)
            response = handler(request, **values)
        except HTTPException, e:
            response = e
        return ClosingIterator(response(environ, start_response),
                               [session.remove, local_manager.cleanup])

    def __call__(self, environ, start_response):
        return self.dispatch(environ, start_response)
