import os, pytest
from data import database
from config import settings
from api.auth import seed_default_users

TEST_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_oasis.db")


@pytest.fixture(autouse=True)
def _test_db():
    old_dir = settings.OASIS_DB_DIR
    old_path = settings.OASIS_DB_PATH
    settings.OASIS_DB_DIR = os.path.dirname(TEST_DB)
    settings.OASIS_DB_PATH = TEST_DB
    database.DB_DIR = settings.OASIS_DB_DIR
    database.DB_PATH = settings.OASIS_DB_PATH
    if "conn" in database._local.__dict__:
        try:
            database._local.conn.close()
        except Exception:
            pass
        del database._local.conn
    if os.path.exists(TEST_DB):
        try:
            os.remove(TEST_DB)
        except PermissionError:
            pass
    database.init_db()
    seed_default_users()
    yield
    settings.OASIS_DB_DIR = old_dir
    settings.OASIS_DB_PATH = old_path
