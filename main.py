import asyncio

import typer

from src.app import WaywatchApp
from src.report import print_report

app = typer.Typer(help="waywatch — a live activity tracker & dashboard for Hyprland")


@app.command()
def tui() -> None:
    """Launch the live tracking dashboard."""
    WaywatchApp().run()


@app.command()
def report(
    period: str = typer.Option("today", "--period", "-p", help="today, week, or month"),
) -> None:
    """Print a quick activity summary without launching the dashboard."""
    if period not in ("today", "week", "month"):
        typer.echo("--period must be one of: today, week, month", err=True)
        raise typer.Exit(code=1)
    asyncio.run(print_report(period))


@app.callback(invoke_without_command=True)
def default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        tui()


if __name__ == "__main__":
    app()
