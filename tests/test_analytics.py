import datetime as dt

import pytest

from src import analytics, categories, db
from src.config import Config


@pytest.fixture
def config():
    return Config(
        work_apps=["code"],
        communication_apps=["slack"],
        entertainment_apps=["spotify"],
        browser_apps=["zen"],
        learning_keywords=["tutorial"],
        streaming_keywords=["youtube"],
        communication_keywords=[],
    )


@pytest.fixture(autouse=True)
def patch_config(monkeypatch, config):
    monkeypatch.setattr(categories, "get_config", lambda: config)


async def _insert_session(app: str, title: str, start: dt.datetime, duration_seconds: float) -> None:
    await db.database.execute(
        db.sessions.insert().values(
            app=app,
            title=title,
            start=start,
            end=start + dt.timedelta(seconds=duration_seconds),
            duration_seconds=duration_seconds,
        )
    )


async def test_category_totals_sums_by_category(isolated_db):
    today = dt.date.today()
    start = dt.datetime.combine(today, dt.time(10, 0))
    await _insert_session("code", "app.py", start, 100.0)
    await _insert_session("zen", "funny cats - youtube", start, 50.0)

    totals = await analytics.category_totals(today, today)

    assert totals["Work"] == 100.0
    assert totals["Watching"] == 50.0
    assert totals["Learning"] == 0.0


async def test_category_totals_only_counts_given_range(isolated_db):
    today = dt.date.today()
    yesterday = today - dt.timedelta(days=1)
    await _insert_session("code", "app.py", dt.datetime.combine(yesterday, dt.time(10, 0)), 100.0)

    totals = await analytics.category_totals(today, today)

    assert totals["Work"] == 0.0


async def test_dominant_app_categories_picks_majority_category(isolated_db):
    today = dt.date.today()
    start = dt.datetime.combine(today, dt.time(10, 0))
    # zen spends more time on a plain browsing tab than on a youtube tab today
    await _insert_session("zen", "GitHub - repo", start, 300.0)
    await _insert_session("zen", "funny cats - youtube", start, 60.0)

    dominant = await analytics.dominant_app_categories(today, today)

    assert dominant["zen"] == "Browsing"


async def test_daily_history_reports_work_seconds_and_session_count(isolated_db):
    today = dt.date.today()
    start = dt.datetime.combine(today, dt.time(9, 0))
    await _insert_session("code", "app.py", start, 120.0)
    await _insert_session("slack", "#general", start, 30.0)

    history = await analytics.daily_history(days=1)

    assert len(history) == 1
    row = history[0]
    assert row["day"] == today
    assert row["total_seconds"] == 150.0
    assert row["work_seconds"] == 120.0
    assert row["session_count"] == 2
    assert row["top_app"] == "code"
