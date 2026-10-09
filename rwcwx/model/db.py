"""
Modified from https://github.com/rshk/flask-sqlalchemy-core/blob/master/flask_sqlalchemy_core/__init__.py
"""
import logging
import os
from contextlib import contextmanager

from sqlalchemy import create_engine, event, exc, MetaData
from sqlalchemy.engine import Engine, ResultProxy
from sqlalchemy.orm import sessionmaker, Session

from werkzeug.local import Local, release_local, LocalManager

logger = logging.getLogger(__name__)
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


def _install_pool_guards(engine: Engine) -> None:
    """
    Make every pooled connection safe to hand out. On each checkout, in this order:

    1. Never reuse a connection opened by another process. If a process forks while a connection sits in the
       pool (uWSGI without lazy-apps loads the app in its master and then forks the workers), every worker
       inherits the same MySQL socket, and concurrent use of it fails with "Lost connection to MySQL server
       during query", i.e. a 500 per worker after each start or reload. The connection is detached *without
       closing it*, because closing would send COM_QUIT on the socket the parent and siblings still share.
       (Recipe from the SQLAlchemy 1.4 docs, "Using Connection Pools with Multiprocessing or os.fork()".)
    2. Ping it, and reconnect if MySQL has dropped it (server restart, wait_timeout). This replaces
       pool_pre_ping=True, which in SQLAlchemy 1.4 pings *before* checkout listeners run, i.e. it would ping
       an inherited socket from several processes at once, which can hang a worker.

    Raising DisconnectionError makes the pool discard the record and transparently open a new connection.
    """
    @event.listens_for(engine, "connect")
    def _tag_pid(dbapi_connection, connection_record):
        connection_record.info["pid"] = os.getpid()

    @event.listens_for(engine, "checkout")
    def _check_connection(dbapi_connection, connection_record, connection_proxy):
        pid = os.getpid()
        owner = connection_record.info.get("pid")
        if owner != pid:
            logger.info("Discarding pooled DB connection opened by pid %s (now pid %s)", owner, pid)
            connection_record.connection = connection_proxy.connection = None
            raise exc.DisconnectionError(f"Connection opened by pid {owner}, checked out in pid {pid}")
        try:
            dbapi_connection.ping(False)
        except Exception as e:
            logger.warning("Pooled DB connection failed ping, reconnecting: %s", e)
            raise exc.DisconnectionError(f"Ping failed: {e}") from e


class Db:

    def __init__(self, database_url: str, **options):
        self._local = Local()
        self._local_manager = LocalManager([self._local])
        self._database_url = database_url
        self._options = options
        self.engine: Engine = self.create_engine()
        self.metadata = MetaData()
        self.session_mkr = sessionmaker(bind=self.engine)
        self.session = self.session_mkr(autocommit=True)  # type: Session

    def create_engine(self) -> Engine:
        engine = create_engine(self._database_url, **self._options)
        _install_pool_guards(engine)
        return engine

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

    def execute_batch(self, records: list) -> None:
        with self.connect() as conn:
            for r in records:
                conn.execute(r)
