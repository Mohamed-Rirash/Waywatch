from __future__ import annotations

from rich.text import Text

_BAR_LEVELS = " ▁▂▃▄▅▆▇█"


def format_hm(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}m"


def bar_chart(
    values: list[float],
    *,
    height: int = 8,
    color: str = "cyan",
    highlight_index: int | None = None,
    highlight_color: str = "green",
    value_formatter=format_hm,
) -> Text:
    """Render a vertical unicode bar chart with a left-hand value scale."""
    max_value = max(values) if values and max(values) > 0 else 1.0
    subunits = [min(height * 8, round((v / max_value) * height * 8)) for v in values]

    scale_width = max(len(value_formatter(max_value)), 4)
    chart = Text()
    for row in range(height):
        row_from_bottom = height - 1 - row
        scale_value = max_value * (row_from_bottom + 1) / height
        label = value_formatter(scale_value) if row % 2 == 0 else ""
        chart.append(label.rjust(scale_width), style="dim")
        chart.append(" ┤" if row != height - 1 else " └", style="dim")

        for col, units in enumerate(subunits):
            level = max(0, min(8, units - row_from_bottom * 8))
            char = _BAR_LEVELS[level]
            bar_color = highlight_color if col == highlight_index else color
            style = bar_color if level > 0 else "dim"
            chart.append(char * 2, style=style)
        chart.append("\n")

    return chart


def progress_bar(width: int, value_pct: float, *, on: str = "green", off: str = "dim") -> Text:
    """Render a single-line filled/unfilled bar, typr-style, using vertical bar glyphs."""
    value_pct = max(0.0, min(100.0, value_pct))
    filled = round(width * value_pct / 100)
    bar = Text()
    bar.append("┃" * filled, style=on)
    bar.append("┃" * (width - filled), style=off)
    return bar


def ranked_bar_list(
    rows: list[tuple[str, float]], *, width: int = 24, color: str = "green", name_width: int = 14
) -> Text:
    """Render a leaderboard: name, an inline horizontal bar relative to the top value, and its time."""
    text = Text()
    if not rows:
        text.append("No data yet.", style="dim")
        return text

    max_value = max(v for _, v in rows) or 1.0
    for name, seconds in rows:
        pct = (seconds / max_value) * 100
        label = name if len(name) <= name_width else name[: name_width - 1] + "…"
        text.append(label.ljust(name_width), style="bold")
        text.append(" ")
        text.append_text(progress_bar(width, pct, on=color))
        text.append(f" {format_hm(seconds)}\n")
    return text
