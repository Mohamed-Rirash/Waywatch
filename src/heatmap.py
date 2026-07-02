from __future__ import annotations

import datetime as dt

from rich.text import Text

_LEVEL_COLORS = ["#30363d", "#0e4429", "#006d32", "#26a641", "#39d353"]
_GUTTER = 5


def _bucket(value: float, thresholds: list[float]) -> int:
    if value <= 0:
        return 0
    for i, threshold in enumerate(thresholds):
        if value <= threshold:
            return i + 1
    return len(thresholds) + 1


def render_heatmap(
    totals: dict[dt.date, float], *, weeks: int = 18, today: dt.date | None = None
) -> Text:
    """Render a GitHub-style Sun-Sat activity calendar for the last `weeks` weeks."""
    today = today or dt.date.today()
    days_since_sunday = (today.weekday() + 1) % 7
    week_end = today + dt.timedelta(days=6 - days_since_sunday)
    start = week_end - dt.timedelta(weeks=weeks - 1, days=6)

    columns = [
        [start + dt.timedelta(weeks=w, days=d) for d in range(7)] for w in range(weeks)
    ]

    values = sorted(v for v in totals.values() if v > 0)
    if values:
        thresholds = [
            values[int(len(values) * 0.25)],
            values[int(len(values) * 0.5)],
            values[int(len(values) * 0.75)],
        ]
    else:
        thresholds = [0.0, 0.0, 0.0]

    total_width = weeks * 2
    month_buffer = [" "] * total_width
    last_month = None
    for idx, week in enumerate(columns):
        month = week[0].strftime("%b")
        if month != last_month:
            last_month = month
            for i, ch in enumerate(month):
                if idx * 2 + i < total_width:
                    month_buffer[idx * 2 + i] = ch

    chart = Text()
    chart.append(" " * _GUTTER)
    chart.append("".join(month_buffer), style="dim")
    chart.append("\n")

    weekday_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    for row in range(7):
        label = weekday_names[row].ljust(_GUTTER) if row % 2 == 1 else " " * _GUTTER
        chart.append(label, style="dim")
        for week in columns:
            day = week[row]
            if day > today:
                chart.append("  ")
                continue
            level = _bucket(totals.get(day, 0.0), thresholds)
            chart.append("██", style=_LEVEL_COLORS[level])
        chart.append("\n")

    return chart
