from __future__ import annotations

from .config import get_config

CATEGORY_ORDER = ["Work", "Learning", "Watching", "Entertainment", "Communication", "Browsing", "Other"]

CATEGORY_COLORS = {
    "Work": "green",
    "Learning": "blue",
    "Watching": "red",
    "Entertainment": "magenta",
    "Communication": "yellow",
    "Browsing": "cyan",
    "Other": "grey62",
}


def categorize(app: str, title: str) -> str:
    """Best-effort classification of a window into a category, using the app name
    and title (browser tab titles usually carry enough signal to tell work from chill,
    and to tell a YouTube tutorial apart from a YouTube video watched for fun).

    Rules come from the user's config (~/.config/waywatch/config.toml), so apps and
    keywords can be tuned without touching code.
    """
    config = get_config()
    app_l = (app or "").lower()
    title_l = (title or "").lower()

    if any(keyword in title_l for keyword in config.learning_keywords):
        return "Learning"
    if any(keyword in title_l for keyword in config.streaming_keywords):
        return "Watching"
    if any(name in app_l for name in config.work_apps):
        return "Work"
    if any(name in app_l for name in config.communication_apps) or any(
        keyword in title_l for keyword in config.communication_keywords
    ):
        return "Communication"
    if any(name in app_l for name in config.entertainment_apps):
        return "Entertainment"
    if any(name in app_l for name in config.browser_apps):
        return "Browsing"
    return "Other"
