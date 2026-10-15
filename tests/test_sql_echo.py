import os
import subprocess
import sys

CODE = "import logging, rwcwx.model.db as d; print(d.SQL_ECHO, logging.getLogger('sqlalchemy.engine').level)"


def _run(env_extra):
    env = {k: v for k, v in os.environ.items() if k != "RWCWX_SQL_ECHO"}
    env.update(env_extra)
    return subprocess.run([sys.executable, "-c", CODE], env=env, capture_output=True, text=True,
                          cwd=os.path.dirname(os.path.dirname(__file__))).stdout.strip()


def test_sql_echo_off_by_default():
    assert _run({}) == "False 30"


def test_sql_echo_opt_in():
    assert _run({"RWCWX_SQL_ECHO": "1"}) == "True 20"
