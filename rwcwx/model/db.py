"""
Modified from https://github.com/rshk/flask-sqlalchemy-core/blob/master/flask_sqlalchemy_core/__init__.py
"""
import logging
from contextlib import contextmanager

from sqlalchemy import create_engine, MetaData
from sqlalchemy.engine import ResultProxy
from sqlalchemy.orm import sessionmaker, Session

from werkzeug.local import Local, release_local, LocalManager

logger = logging.getLogger(__name__)
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


class Db:

    def __init__(self, database_url: str, **options):
        self._local = Local()
        self._local_manager = LocalManager([self._local])
        self._database_url = database_url
        self._options = options
        self.engine = self.create_engine()
        self.metadata = MetaData()
        self.session_mkr = sessionmaker(bind=self.engine)
        self.session = self.session_mkr(autocommit=True)  # type: Session

    def create_engine(self):
        return create_engine(self._database_url, **self._options)

    def connect(self):
        try:
            self._local.connection
        except AttributeError:
            return self._new_connection_context()
        return self._reuse_connection_context()

    @property
    def s(self) -> Session:
        return self.session

    @contextmanager
    def _new_connection_context(self):
        logger.debug('[%s] Getting new connection from pool', self._local_manager.get_ident())
        conn = self.engine.connect()
        self._local.connection = conn
        yield conn
        logger.debug('[%s] Releasing connection to pool', self._local_manager.get_ident())
        self._local.connection = None
        release_local(self._local)
        conn.close()

    @contextmanager
    def _reuse_connection_context(self):
        logger.debug('[%s] Reusing connection', self._local_manager.get_ident())
        yield self._local.connection
        logger.debug('[%s] Finished using connection', self._local_manager.get_ident())

    @contextmanager
    def transaction(self, autocommit=True, rollback=False):
        with self.connect() as conn:
            logger.debug('[%s] Starting transaction', self._local_manager.get_ident())
            trans = conn.begin_nested()
            try:
                yield conn

                if autocommit:
                    logger.debug('[%s] Committing transaction', self._local_manager.get_ident())
                    trans.commit()

                if rollback:
                    logger.debug('[%s] Rolling back transaction', self._local_manager.get_ident())
                    trans.rollback()

            except Exception:
                logger.debug('[%s] Rolling back transaction (exception)',
                             self._local_manager.get_ident())
                trans.rollback()
                raise

    def execute(self, *args, **kwargs) -> ResultProxy:
        with self.connect() as conn:
            return conn.execute(*args, **kwargs)
