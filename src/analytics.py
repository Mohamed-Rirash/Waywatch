from __future__ import annotations

import datetime as dt

from . import db
from .categories import CATEGORY_ORDER, categorize

EPOCH = dt.date(2000, 1, 1)


async def category_totals(start_day: dt.date, end_day: dt.date) -> dict[str, float]:
    """Total tracked seconds per category between start_day and end_day (inclusive)."""
    rows = await db.app_title_totals(start_day, end_day)
    totals: dict[str, float] = {category: 0.0 for category in CATEGORY_ORDER}
    for row in rows:
        category = categorize(row["app"], row["title"])
        totals[category] += row["total_seconds"] or 0.0
    return totals


async def dominant_app_categories(start_day: dt.date, end_day: dt.date) -> dict[str, str]:
    """For each app, the category it spent the most time in (titles can shift an app's
    category, e.g. a browser mostly on YouTube should read as Entertainment, not Browsing)."""
    rows = await db.app_title_totals(start_day, end_day)
    per_app: dict[str, dict[str, float]] = {}
    for row in rows:
        category = categorize(row["app"], row["title"])
        bucket = per_app.setdefault(row["app"], {})
        bucket[category] = bucket.get(category, 0.0) + (row["total_seconds"] or 0.0)
    return {app: max(cats.items(), key=lambda kv: kv[1])[0] for app, cats in per_app.items()}


async def daily_history(days: int = 8) -> list[dict]:
    """Per-day rollups (total time, work time, session count, top app) for the last `days` days."""
    end = dt.date.today()
    start = end - dt.timedelta(days=days - 1)
    totals = await db.daily_totals(start, end)

    result = []
    for offset in range(days):
        day = start + dt.timedelta(days=offset)
        app_rows = await db.today_summary(day)
        day_categories = await category_totals(day, day)
        result.append(
            {
                "day": day,
                "total_seconds": totals.get(day, 0.0),
                "work_seconds": day_categories.get("Work", 0.0),
                "session_count": await db.today_session_count(day),
                "top_app": app_rows[0]["app"] if app_rows else "—",
            }
        )
    return result
