import pytest

from src import db


@pytest.fixture
async def isolated_db(tmp_path):
    """Point the database at a throwaway directory so tests never touch the real
    ~/.local/share/waywatch/activity.sqlite3."""
    db.configure(tmp_path)
    db.create_tables()
    await db.database.connect()
    yield
    await db.database.disconnect()
