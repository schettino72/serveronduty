import os

from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import scoped_session, sessionmaker


metadata = MetaData()

def get_sa_db_uri(driver='', username='', password='', host='', port='', database=''):
    """get SQLAlchemy DB URI: driver://username:password@host:port/database"""
    assert driver
    if driver == 'sqlite':
        # get absolute file path
        if not database.startswith('/'):
            db_file = os.path.abspath(database)
        else:
            db_file = database
        db_uri = '%s:///%s' % (driver, db_file)
    else:
        db_uri = ('%s://%s:%s@%s:%s/%s' %
                  (driver, username, password, host, port, database))
    return db_uri


class DB(object):
    def __init__(self, db_uri):
        self.engine = create_engine(db_uri, convert_unicode=True)
        self.session = scoped_session(
            sessionmaker(autocommit=False,
                         autoflush=False,
                         bind=self.engine))

    def init_database(self):
        metadata.create_all(bind=self.engine)




