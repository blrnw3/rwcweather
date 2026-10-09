"""
Pool safety tests for rwcwx.model.db.Db (needs the dev MySQL; skipped otherwise).
Run: . dev/box/env.sh; venv/bin/python -m unittest tests.test_db_pool
"""
import os
import unittest

from sqlalchemy import text

from rwcwx.model.db import Db

URL = f"mysql://{os.getenv('MYSQL_URL', 'root:test@127.0.0.1:3307/wx')}"


def _db() -> Db:
    return Db(URL, pool_recycle=3600)


def _conn_id(db: Db) -> int:
    with db.engine.connect() as c:
        return c.execute(text("SELECT CONNECTION_ID()")).scalar()


try:
    _conn_id(_db())
    DB_OK = True
except Exception:  # pragma: no cover
    DB_OK = False


@unittest.skipUnless(DB_OK, "dev MySQL not reachable")
class PoolGuardTest(unittest.TestCase):

    def test_forked_children_do_not_share_parent_connection(self):
        db = _db()
        parent_id = _conn_id(db)  # leaves an open connection in the pool, as table reflection does at import
        children = []
        for _ in range(4):
            r, w = os.pipe()
            pid = os.fork()
            if pid == 0:  # child: hammer the pool concurrently with its siblings
                os.close(r)
                try:
                    ids = {_conn_id(db) for _ in range(20)}
                    os.write(w, ",".join(map(str, sorted(ids))).encode())
                    os._exit(0)
                except BaseException as e:  # report and fail
                    os.write(w, f"ERR {e!r}".encode())
                    os._exit(1)
            os.close(w)
            children.append((pid, r))
        child_ids = []
        for pid, r in children:
            out = os.read(r, 4096).decode()
            os.close(r)
            _, status = os.waitpid(pid, 0)
            self.assertEqual(status, 0, out)
            ids = [int(x) for x in out.split(",")]
            self.assertEqual(len(ids), 1, "each child should keep reusing its own single connection")
            child_ids.append(ids[0])
        self.assertNotIn(parent_id, child_ids, "a child reused the parent's MySQL connection")
        self.assertEqual(len(set(child_ids)), 4, "children must not share a connection")
        self.assertEqual(_conn_id(db), parent_id, "parent keeps its own connection")

    def test_dropped_connection_is_replaced_transparently(self):
        db = _db()
        first = _conn_id(db)
        with _db().engine.connect() as admin:  # simulate MySQL dropping it (restart / wait_timeout)
            admin.execute(text(f"KILL {first}"))
        second = _conn_id(db)  # must not raise
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
