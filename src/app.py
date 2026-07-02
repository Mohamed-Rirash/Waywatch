from __future__ import annotations

import datetime as dt

from rich import box
from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Static

from . import analytics, db
from .categories import CATEGORY_COLORS, CATEGORY_ORDER, categorize
from .charts import bar_chart, format_hm, progress_bar, ranked_bar_list
from .config import get_config
from .heatmap import render_heatmap
from .hypr import get_active_window
from .idle import get_cursor_pos

BAR_WIDTH = 30
PANE_NAMES = ["home", "trends", "apps", "titles"]
HEATMAP_LEGEND_COLORS = ["#30363d", "#0e4429", "#006d32", "#26a641", "#39d353"]


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def app_badges(ranked: list[tuple[str, float]], dominant: dict[str, str]) -> Text:
    text = Text()
    if not ranked:
        text.append("No activity tracked yet today.", style="dim")
        return text
    for i, (app_name, _seconds) in enumerate(ranked):
        category = dominant.get(app_name, "Other")
        text.append(f" {app_name} ", style=f"bold {CATEGORY_COLORS[category]}")
        text.append(" ")
        if (i + 1) % 4 == 0:
            text.append("\n")
    return text


class WaywatchApp(App):
    """Live activity tracker & dashboard for Hyprland, styled after nvzone/typr."""

    TITLE = "waywatch"
    CSS = """
    #live {
        height: 4;
        border: round $accent;
        padding: 0 1;
        content-align: left middle;
    }
    #panes {
        height: 1fr;
    }
    #panes > Vertical {
        width: 1fr;
        height: 100%;
    }
    #panes Static, #panes DataTable {
        border: round $primary;
        padding: 0 1;
    }
    #home-hourly, #apps-heatmap {
        height: auto;
    }
    #panes > Vertical > Horizontal {
        height: auto;
    }
    #trends-week, #trends-month {
        width: 1fr;
        height: auto;
    }
    #apps-longest, #apps-shortest, #apps-overall {
        width: 1fr;
        height: auto;
    }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+t", "cycle_panes", "Cycle panes"),
        ("r", "toggle_heatmap_range", "Toggle range"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._config = get_config()
        self._session_id: int | None = None
        self._current_app: str | None = None
        self._current_title: str = ""
        self._session_start: dt.datetime | None = None
        self._ticks = 0
        self._pane_index = 0
        self._heatmap_weeks_back = 0
        self._overall: dict = {}
        self._last_cursor_pos: tuple[int, int] | None = None
        self._last_activity = dt.datetime.now()
        self._is_idle = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Starting...", id="live")
        with Horizontal(id="panes"):
            with Vertical(id="pane-home"):
                yield Static(id="home-categories")
                yield Static(id="home-stats")
                yield Static(id="home-apps")
                yield Static(id="home-hourly")
            with Vertical(id="pane-trends"):
                with Horizontal():
                    yield Static(id="trends-week")
                    yield Static(id="trends-month")
                yield Static(id="trends-categories")
                yield DataTable(id="trends-history")
            with Vertical(id="pane-apps"):
                yield Static(id="apps-badges")
                with Horizontal():
                    yield Static(id="apps-longest")
                    yield Static(id="apps-shortest")
                    yield Static(id="apps-overall")
                yield Static(id="apps-heatmap")
            with Vertical(id="pane-titles"):
                yield Static(id="titles-now")
                yield Static(id="titles-others")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#home-categories", Static).border_title = "Work vs. chill — today"
        self.query_one("#home-stats", Static).border_title = "Today's stats"
        self.query_one("#home-apps", Static).border_title = "What I was doing"
        self.query_one("#home-hourly", Static).border_title = "Today by hour"
        self.query_one("#trends-week", Static).border_title = "Most used apps — this week"
        self.query_one("#trends-month", Static).border_title = "Most used apps — this month"
        self.query_one("#trends-categories", Static).border_title = "This week vs. last week"
        self.query_one("#trends-history", DataTable).border_title = "Last 8 days"
        self.query_one("#apps-badges", Static).border_title = "Apps by category"
        self.query_one("#apps-longest", Static).border_title = "Longest sessions"
        self.query_one("#apps-shortest", Static).border_title = "Shortest sessions"
        self.query_one("#apps-overall", Static).border_title = "Overall stats"
        self.query_one("#apps-heatmap", Static).border_title = "Activity heatmap"
        self.query_one("#titles-now", Static).border_title = "Right now"
        self.query_one("#titles-others", Static).border_title = "Also today"

        history_table = self.query_one("#trends-history", DataTable)
        history_table.add_columns("Date", "Total", "Work", "Sessions", "Top app", "Goal")
        history_table.cursor_type = "row"

        self._apply_pane_visibility()

        db.create_tables()
        await db.database.connect()
        self.set_interval(self._config.poll_interval_seconds, self.tick)

    async def on_unmount(self) -> None:
        await self._close_current_session()
        await db.database.disconnect()

    def action_cycle_panes(self) -> None:
        self._pane_index = (self._pane_index + 1) % len(PANE_NAMES)
        self._apply_pane_visibility()

    def action_toggle_heatmap_range(self) -> None:
        self._heatmap_weeks_back = 18 if self._heatmap_weeks_back == 0 else 0

    def _apply_pane_visibility(self) -> None:
        visible = {self._pane_index, (self._pane_index + 1) % len(PANE_NAMES)}
        for i, name in enumerate(PANE_NAMES):
            self.query_one(f"#pane-{name}", Vertical).display = i in visible

    async def tick(self) -> None:
        self._ticks += 1
        await self._update_idle_state()
        if not self._is_idle:
            await self._poll_window()
        self._refresh_live()
        await self._refresh_home_pane()
        await self._refresh_apps_pane()
        await self._refresh_titles_pane()
        if self._ticks % 5 == 1:
            await self._refresh_trends_pane()

    async def _update_idle_state(self) -> None:
        """Cursor movement is used as a proxy for "still here" — Hyprland doesn't expose
        an idle timer over hyprctl. If the cursor hasn't moved for a while, the currently
        open session is closed at the last-seen activity time (trimming the idle tail),
        and tracking pauses until the cursor moves again."""
        pos = await get_cursor_pos()
        now = dt.datetime.now()

        if pos is not None and pos != self._last_cursor_pos:
            self._last_cursor_pos = pos
            self._last_activity = now
            if self._is_idle:
                self._is_idle = False
                self._current_app = None
                self._current_title = ""
            return

        idle_for = (now - self._last_activity).total_seconds()
        if not self._is_idle and idle_for >= self._config.idle_threshold_seconds:
            self._is_idle = True
            await self._close_current_session(end=self._last_activity)
            self._current_app = None
            self._current_title = ""
            self._session_start = None
            self._session_id = None

    async def _poll_window(self) -> None:
        window = await get_active_window()
        app_name, title = window if window else (None, "")

        if app_name == self._current_app and title == self._current_title:
            return

        await self._close_current_session()

        self._current_app = app_name
        self._current_title = title
        if app_name is not None:
            self._session_start = dt.datetime.now()
            self._session_id = await db.start_session(app_name, title, self._session_start)
        else:
            self._session_start = None
            self._session_id = None

    async def _close_current_session(self, end: dt.datetime | None = None) -> None:
        if self._session_id is not None and self._session_start is not None:
            end = end or dt.datetime.now()
            duration = (end - self._session_start).total_seconds()
            await db.end_session(self._session_id, end, duration)

    def _refresh_live(self) -> None:
        live = self.query_one("#live", Static)
        if self._current_app and self._session_start:
            elapsed = (dt.datetime.now() - self._session_start).total_seconds()
            category = categorize(self._current_app, self._current_title)
            text = Text()
            text.append(self._current_app, style="bold")
            text.append(f" — {self._current_title}\n")
            text.append(f"tracking for {format_duration(elapsed)}   ")
            text.append(f" {category} ", style=f"bold reverse {CATEGORY_COLORS[category]}")
            live.update(text)
        elif self._is_idle:
            away_for = (dt.datetime.now() - self._last_activity).total_seconds()
            live.update(Text(f"😴 Away — idle for {format_duration(away_for)}", style="dim"))
        else:
            live.update(Text("Idle — no focused window", style="dim"))

    def _open_session_elapsed(self) -> float:
        if self._current_app and self._session_start:
            return (dt.datetime.now() - self._session_start).total_seconds()
        return 0.0

    async def _today_ranked_totals(self) -> tuple[list[tuple[str, float]], float]:
        today = dt.date.today()
        rows = await db.today_summary(today)
        totals: dict[str, float] = {row["app"]: row["total_seconds"] or 0.0 for row in rows}
        if self._current_app:
            totals[self._current_app] = totals.get(self._current_app, 0.0) + self._open_session_elapsed()
        ranked = sorted(totals.items(), key=lambda kv: -kv[1])
        return ranked, sum(totals.values())

    async def _today_category_totals(self, today: dt.date) -> dict[str, float]:
        categories = await analytics.category_totals(today, today)
        if self._current_app:
            category = categorize(self._current_app, self._current_title)
            categories[category] = categories.get(category, 0.0) + self._open_session_elapsed()
        return categories

    async def _refresh_home_pane(self) -> None:
        today = dt.date.today()
        ranked, day_total = await self._today_ranked_totals()
        categories = await self._today_category_totals(today)

        work_seconds = categories.get("Work", 0.0)
        work_goal = self._config.work_goal_seconds
        work_pct = min(100.0, (work_seconds / work_goal) * 100)

        cat_text = Text()
        cat_text.append(f"⏱  Work goal ~ {format_hm(work_seconds)} / {format_hm(work_goal)}\n")
        cat_text.append_text(progress_bar(BAR_WIDTH, work_pct, on=CATEGORY_COLORS["Work"]))
        cat_text.append("\n\n")
        for category in CATEGORY_ORDER:
            seconds = categories.get(category, 0.0)
            share_pct = (seconds / day_total * 100) if day_total else 0.0
            cat_text.append(f"{category} ~ {format_hm(seconds)} ({share_pct:.0f}% of today)\n")
            cat_text.append_text(progress_bar(BAR_WIDTH, share_pct, on=CATEGORY_COLORS[category]))
            cat_text.append("\n\n")
        self.query_one("#home-categories", Static).update(cat_text)

        session_count = await db.today_session_count(today)
        stats_table = Table(box=box.SIMPLE_HEAD, expand=True, show_edge=False)
        for col in ("Total", "Work", "Learning", "Watching", "Sessions"):
            stats_table.add_column(col)
        stats_table.add_row(
            format_hm(day_total),
            format_hm(categories.get("Work", 0.0)),
            format_hm(categories.get("Learning", 0.0)),
            format_hm(categories.get("Watching", 0.0)),
            str(session_count),
        )
        self.query_one("#home-stats", Static).update(stats_table)

        dominant = await analytics.dominant_app_categories(today, today)

        apps_table = Table(box=box.SIMPLE_HEAD, show_edge=False, expand=True)
        apps_table.add_column("App")
        apps_table.add_column("Category")
        apps_table.add_column("Time", justify="right")
        apps_table.add_column("Share", justify="right")
        for app_name, seconds in ranked[:8]:
            category = dominant.get(app_name, "Other")
            share_pct = (seconds / day_total * 100) if day_total else 0.0
            apps_table.add_row(
                app_name,
                Text(category, style=CATEGORY_COLORS[category]),
                format_duration(seconds),
                f"{share_pct:.0f}%",
            )
        self.query_one("#home-apps", Static).update(apps_table)

        current_hour = dt.datetime.now().hour
        hourly = await db.hourly_summary(today)
        if self._current_app:
            hourly[current_hour] = hourly.get(current_hour, 0.0) + self._open_session_elapsed()
        hourly_values = [hourly.get(h, 0.0) for h in range(24)]
        self.query_one("#home-hourly", Static).update(
            bar_chart(hourly_values, height=8, color="cyan", highlight_index=current_hour)
        )

    async def _refresh_apps_pane(self) -> None:
        ranked, _day_total = await self._today_ranked_totals()
        today = dt.date.today()
        dominant = await analytics.dominant_app_categories(today, today)

        self.query_one("#apps-badges", Static).update(app_badges(ranked, dominant))

        day_sessions = await db.sessions_for_day(today)
        longest_table = Table(box=box.SIMPLE_HEAD, show_edge=False)
        longest_table.add_column("App")
        longest_table.add_column("Time")
        for row in day_sessions[:5]:
            longest_table.add_row(row["app"], format_duration(row["duration_seconds"]))
        self.query_one("#apps-longest", Static).update(longest_table)

        shortest_table = Table(box=box.SIMPLE_HEAD, show_edge=False)
        shortest_table.add_column("App")
        shortest_table.add_column("Time")
        for row in reversed(day_sessions[-5:]):
            shortest_table.add_row(row["app"], format_duration(row["duration_seconds"]))
        self.query_one("#apps-shortest", Static).update(shortest_table)

        if self._ticks % 5 == 1:
            self._overall = await db.overall_stats()
        overall = self._overall
        stats = self.query_one("#apps-overall", Static)
        stats.update(
            f"Total sessions:     [b]{overall.get('session_count') or 0}[/b]\n"
            f"Total time tracked: [b]{format_hm(overall.get('total_seconds') or 0.0)}[/b]\n"
            f"Average session:    [b]{format_duration(overall.get('avg_seconds') or 0.0)}[/b]\n"
            f"Longest session:    [b]{format_duration(overall.get('max_seconds') or 0.0)}[/b]\n"
            f"Apps tracked ever:  [b]{overall.get('app_count') or 0}[/b]"
        )

        if self._ticks % 5 == 1:
            weeks_back = self._heatmap_weeks_back
            end = today - dt.timedelta(weeks=weeks_back)
            start = end - dt.timedelta(weeks=17, days=6)
            totals = await db.daily_totals(start, end)
            if self._current_app and weeks_back == 0:
                totals[today] = totals.get(today, 0.0) + self._open_session_elapsed()
            heatmap = render_heatmap(totals, today=end)
            heatmap.append("\n")
            heatmap.append("Less ", style="dim")
            for color in HEATMAP_LEGEND_COLORS:
                heatmap.append("██", style=color)
            heatmap.append(" More  ", style="dim")
            heatmap.append("[r] toggle range", style="dim")
            self.query_one("#apps-heatmap", Static).update(heatmap)

    def _title_rows_with_live(self, rows: list[dict], app_name: str) -> list[tuple[str, float]]:
        totals = {row["title"] or "(untitled)": row["total_seconds"] or 0.0 for row in rows}
        if self._current_app == app_name:
            key = self._current_title or "(untitled)"
            totals[key] = totals.get(key, 0.0) + self._open_session_elapsed()
        return sorted(totals.items(), key=lambda kv: -kv[1])

    def _build_title_table(self, rows: list[tuple[str, float]]) -> Table:
        table = Table(box=box.SIMPLE_HEAD, show_edge=False)
        table.add_column("Title", overflow="ellipsis", no_wrap=True, width=55)
        table.add_column("Time", justify="right", width=10, no_wrap=True)
        for title, seconds in rows:
            table.add_row(title, format_duration(seconds))
        return table

    async def _refresh_titles_pane(self) -> None:
        today = dt.date.today()
        ranked, _ = await self._today_ranked_totals()

        now_widget = self.query_one("#titles-now", Static)
        if self._current_app:
            rows = await db.title_summary(today, self._current_app, limit=8)
            title_rows = self._title_rows_with_live(rows, self._current_app)
            header = Text(f"{self._current_app}\n", style="bold green")
            now_widget.update(Group(header, self._build_title_table(title_rows)))
        else:
            now_widget.update(Text("Idle — no focused window", style="dim"))

        others_widget = self.query_one("#titles-others", Static)
        other_apps = [name for name, _ in ranked if name != self._current_app][:2]
        if not other_apps:
            others_widget.update(Text("Nothing else tracked today.", style="dim"))
        else:
            sections = []
            for app_name in other_apps:
                rows = await db.title_summary(today, app_name, limit=5)
                title_rows = self._title_rows_with_live(rows, app_name)
                sections.append(Text(app_name, style="bold yellow"))
                sections.append(self._build_title_table(title_rows))
            others_widget.update(Group(*sections))

    async def _refresh_trends_pane(self) -> None:
        today = dt.date.today()

        week_start = today - dt.timedelta(days=6)
        week_rows = await db.app_totals_range(week_start, today)
        week_ranked = [(r["app"], r["total_seconds"] or 0.0) for r in week_rows[:6]]
        self.query_one("#trends-week", Static).update(
            ranked_bar_list(week_ranked, color="green")
        )

        month_start = today - dt.timedelta(days=29)
        month_rows = await db.app_totals_range(month_start, today)
        month_ranked = [(r["app"], r["total_seconds"] or 0.0) for r in month_rows[:6]]
        self.query_one("#trends-month", Static).update(
            ranked_bar_list(month_ranked, color="magenta")
        )

        this_week = await analytics.category_totals(week_start, today)
        last_week_start = week_start - dt.timedelta(days=7)
        last_week_end = week_start - dt.timedelta(days=1)
        last_week = await analytics.category_totals(last_week_start, last_week_end)

        compare_table = Table(box=box.SIMPLE_HEAD, show_edge=False, expand=True)
        compare_table.add_column("Category")
        compare_table.add_column("This week", justify="right")
        compare_table.add_column("Last week", justify="right")
        compare_table.add_column("Change", justify="right")
        for category in CATEGORY_ORDER:
            current = this_week.get(category, 0.0)
            previous = last_week.get(category, 0.0)
            if previous:
                delta_pct = (current - previous) / previous * 100
                arrow = "▲" if delta_pct > 0 else ("▼" if delta_pct < 0 else "→")
                change = f"{arrow} {abs(delta_pct):.0f}%"
            elif current:
                change = "▲ new"
            else:
                change = "—"
            compare_table.add_row(
                Text(category, style=CATEGORY_COLORS[category]),
                format_hm(current),
                format_hm(previous),
                change,
            )
        self.query_one("#trends-categories", Static).update(compare_table)

        history = await analytics.daily_history(8)
        table = self.query_one("#trends-history", DataTable)
        table.clear()
        for row in reversed(history):
            goal_pct = min(100.0, (row["work_seconds"] / self._config.work_goal_seconds) * 100)
            table.add_row(
                row["day"].strftime("%a %d %b"),
                format_hm(row["total_seconds"]),
                format_hm(row["work_seconds"]),
                str(row["session_count"]),
                row["top_app"],
                progress_bar(12, goal_pct, on=CATEGORY_COLORS["Work"]),
            )
