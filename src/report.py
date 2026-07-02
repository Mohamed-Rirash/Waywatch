from __future__ import annotations

import datetime as dt

from rich import box
from rich.console import Console
from rich.table import Table

from . import analytics, db
from .categories import CATEGORY_COLORS, CATEGORY_ORDER
from .charts import format_hm

PERIOD_DAYS_BACK = {"today": 0, "week": 6, "month": 29}


async def print_report(period: str) -> None:
    """Print a quick activity summary to the terminal, without launching the TUI."""
    if period not in PERIOD_DAYS_BACK:
        raise ValueError(f"Unknown period {period!r} (expected: today, week, month)")

    console = Console()
    db.create_tables()
    await db.database.connect()
    try:
        today = dt.date.today()
        start = today - dt.timedelta(days=PERIOD_DAYS_BACK[period])

        categories = await analytics.category_totals(start, today)
        total = sum(categories.values())

        console.print(f"\n[b]waywatch report[/b] — {period} ({start.isoformat()} to {today.isoformat()})\n")

        if total == 0:
            console.print("[dim]No activity tracked in this period.[/dim]\n")
            return

        console.print(f"Total tracked: [b]{format_hm(total)}[/b]\n")

        category_table = Table(box=box.SIMPLE_HEAD, show_edge=False)
        category_table.add_column("Category")
        category_table.add_column("Time", justify="right")
        category_table.add_column("Share", justify="right")
        for category in CATEGORY_ORDER:
            seconds = categories.get(category, 0.0)
            if seconds == 0:
                continue
            share = seconds / total * 100
            category_table.add_row(
                f"[{CATEGORY_COLORS[category]}]{category}[/]", format_hm(seconds), f"{share:.0f}%"
            )
        console.print(category_table)

        app_rows = await db.app_totals_range(start, today)
        app_table = Table(box=box.SIMPLE_HEAD, show_edge=False)
        app_table.add_column("App")
        app_table.add_column("Time", justify="right")
        app_table.add_column("Share", justify="right")
        for row in app_rows[:10]:
            seconds = row["total_seconds"] or 0.0
            share = seconds / total * 100 if total else 0.0
            app_table.add_row(row["app"], format_hm(seconds), f"{share:.0f}%")
        console.print()
        console.print(app_table)
        console.print()
    finally:
        await db.database.disconnect()
