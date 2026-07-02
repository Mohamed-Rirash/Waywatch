from __future__ import annotations

import datetime as dt
from pathlib import Path

from databases import Database
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    select,
)

DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "waywatch"

metadata = MetaData()

sessions = Table(
    "sessions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("app", String, nullable=False),
    Column("title", String, nullable=False),
    Column("start", DateTime, nullable=False),
    Column("end", DateTime),
    Column("duration_seconds", Float),
)


def _urls_for(data_dir: Path) -> tuple[str, str]:
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "activity.sqlite3"
    return f"sqlite:///{db_path}", f"sqlite+aiosqlite:///{db_path}"


SYNC_DATABASE_URL, ASYNC_DATABASE_URL = _urls_for(DEFAULT_DATA_DIR)
database = Database(ASYNC_DATABASE_URL)


def configure(data_dir: Path) -> None:
    """Point the database at a different data directory. Used by tests to avoid
    touching the real ~/.local/share/waywatch/activity.sqlite3."""
    global SYNC_DATABASE_URL, ASYNC_DATABASE_URL, database
    SYNC_DATABASE_URL, ASYNC_DATABASE_URL = _urls_for(data_dir)
    database = Database(ASYNC_DATABASE_URL)


def create_tables() -> None:
    engine = create_engine(SYNC_DATABASE_URL)
    metadata.create_all(engine)
    engine.dispose()


async def start_session(app: str, title: str, start: dt.datetime) -> int:
    query = sessions.insert().values(app=app, title=title, start=start)
    return await database.execute(query)


async def end_session(session_id: int, end: dt.datetime, duration_seconds: float) -> None:
    query = (
        sessions.update()
        .where(sessions.c.id == session_id)
        .values(end=end, duration_seconds=duration_seconds)
    )
    await database.execute(query)


async def app_totals_range(start_day: dt.date, end_day: dt.date) -> list[dict]:
    """Total tracked seconds per app between start_day and end_day (inclusive), ranked."""
    start_of_range = dt.datetime.combine(start_day, dt.time.min)
    end_of_range = dt.datetime.combine(end_day, dt.time.max)
    query = (
        select(
            sessions.c.app,
            func.sum(sessions.c.duration_seconds).label("total_seconds"),
        )
        .where(
            sessions.c.start >= start_of_range,
            sessions.c.start <= end_of_range,
            sessions.c.duration_seconds.isnot(None),
        )
        .group_by(sessions.c.app)
        .order_by(func.sum(sessions.c.duration_seconds).desc())
    )
    rows = await database.fetch_all(query)
    return [dict(row._mapping) for row in rows]


async def today_summary(day: dt.date) -> list[dict]:
    return await app_totals_range(day, day)


async def app_title_totals(start_day: dt.date, end_day: dt.date) -> list[dict]:
    """Total tracked seconds per (app, title) pair between start_day and end_day (inclusive).

    Used to classify time into categories (work/chill/...), since the category often
    depends on the title (e.g. a YouTube tab) as well as the app.
    """
    start_of_range = dt.datetime.combine(start_day, dt.time.min)
    end_of_range = dt.datetime.combine(end_day, dt.time.max)
    query = (
        select(
            sessions.c.app,
            sessions.c.title,
            func.sum(sessions.c.duration_seconds).label("total_seconds"),
        )
        .where(
            sessions.c.start >= start_of_range,
            sessions.c.start <= end_of_range,
            sessions.c.duration_seconds.isnot(None),
        )
        .group_by(sessions.c.app, sessions.c.title)
    )
    rows = await database.fetch_all(query)
    return [dict(row._mapping) for row in rows]


async def title_summary(day: dt.date, app: str, limit: int = 8) -> list[dict]:
    """Top titles (tabs/files/windows) for one app on a given day, e.g. browser tabs or editor files."""
    start_of_day = dt.datetime.combine(day, dt.time.min)
    end_of_day = dt.datetime.combine(day, dt.time.max)
    query = (
        select(
            sessions.c.title,
            func.sum(sessions.c.duration_seconds).label("total_seconds"),
        )
        .where(
            sessions.c.app == app,
            sessions.c.start >= start_of_day,
            sessions.c.start <= end_of_day,
            sessions.c.duration_seconds.isnot(None),
        )
        .group_by(sessions.c.title)
        .order_by(func.sum(sessions.c.duration_seconds).desc())
        .limit(limit)
    )
    rows = await database.fetch_all(query)
    return [dict(row._mapping) for row in rows]


async def hourly_summary(day: dt.date) -> dict[int, float]:
    """Total tracked seconds per hour (0-23) for the given day."""
    start_of_day = dt.datetime.combine(day, dt.time.min)
    end_of_day = dt.datetime.combine(day, dt.time.max)
    hour = func.cast(func.strftime("%H", sessions.c.start), Integer)
    query = (
        select(hour.label("hour"), func.sum(sessions.c.duration_seconds).label("total_seconds"))
        .where(
            sessions.c.start >= start_of_day,
            sessions.c.start <= end_of_day,
            sessions.c.duration_seconds.isnot(None),
        )
        .group_by(hour)
    )
    rows = await database.fetch_all(query)
    return {row["hour"]: row["total_seconds"] or 0.0 for row in rows}


async def daily_totals(start_day: dt.date, end_day: dt.date) -> dict[dt.date, float]:
    """Total tracked seconds per calendar day between start_day and end_day (inclusive)."""
    start_of_range = dt.datetime.combine(start_day, dt.time.min)
    end_of_range = dt.datetime.combine(end_day, dt.time.max)
    day = func.date(sessions.c.start)
    query = (
        select(day.label("day"), func.sum(sessions.c.duration_seconds).label("total_seconds"))
        .where(
            sessions.c.start >= start_of_range,
            sessions.c.start <= end_of_range,
            sessions.c.duration_seconds.isnot(None),
        )
        .group_by(day)
    )
    rows = await database.fetch_all(query)
    return {
        dt.date.fromisoformat(row["day"]): row["total_seconds"] or 0.0 for row in rows
    }


async def today_session_count(day: dt.date) -> int:
    start_of_day = dt.datetime.combine(day, dt.time.min)
    end_of_day = dt.datetime.combine(day, dt.time.max)
    query = select(func.count(sessions.c.id)).where(
        sessions.c.start >= start_of_day,
        sessions.c.start <= end_of_day,
    )
    return await database.fetch_val(query) or 0


async def overall_stats() -> dict:
    query = select(
        func.count(sessions.c.id).label("session_count"),
        func.sum(sessions.c.duration_seconds).label("total_seconds"),
        func.avg(sessions.c.duration_seconds).label("avg_seconds"),
        func.max(sessions.c.duration_seconds).label("max_seconds"),
        func.count(func.distinct(sessions.c.app)).label("app_count"),
    ).where(sessions.c.duration_seconds.isnot(None))
    row = await database.fetch_one(query)
    return dict(row._mapping) if row else {}


async def sessions_for_day(day: dt.date) -> list[dict]:
    """Individual closed sessions for a day, longest first."""
    start_of_day = dt.datetime.combine(day, dt.time.min)
    end_of_day = dt.datetime.combine(day, dt.time.max)
    query = (
        select(sessions.c.app, sessions.c.title, sessions.c.duration_seconds)
        .where(
            sessions.c.start >= start_of_day,
            sessions.c.start <= end_of_day,
            sessions.c.duration_seconds.isnot(None),
        )
        .order_by(sessions.c.duration_seconds.desc())
    )
    rows = await database.fetch_all(query)
    return [dict(row._mapping) for row in rows]


async def recent_sessions(limit: int = 10) -> list[dict]:
    """The most recent closed sessions, newest first."""
    query = (
        select(sessions.c.app, sessions.c.duration_seconds)
        .where(sessions.c.duration_seconds.isnot(None))
        .order_by(sessions.c.start.desc())
        .limit(limit)
    )
    rows = await database.fetch_all(query)
    return [dict(row._mapping) for row in rows]
