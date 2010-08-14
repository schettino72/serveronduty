import os
import sys

import yaml
from flask import Flask

from websod import database


# required by Flask framework
app = Flask(__name__)

@app.after_request
def shutdown_session(response):
    """ close SQLAlchemy session"""
    app.db.session.remove()
    return response


def setup_app(flask_app, config):
    # set config
    flask_app.config.update(config)

    # set DB
    db_uri = database.get_sa_db_uri(**config['db'])
    flask_app.db = database.DB(db_uri)


##################################


# this should be at the bottom - circular import to register views.
import websod.views
websod.views # keep pyflakes quiet
