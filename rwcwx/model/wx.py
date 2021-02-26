from sqlalchemy import Table

from rwcwx.model.db import Db


class Model(object):

    def __init__(self, db: Db):
        self._db = db

        self.obs = Table("obs", self._db.metadata, autoload=True, autoload_with=self._db.engine)
