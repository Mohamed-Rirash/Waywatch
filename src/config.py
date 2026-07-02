from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "waywatch"
CONFIG_PATH = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG_TOML = """\
# waywatch configuration
# Edit this file to tune tracking and how apps/tabs are categorized, then
# restart waywatch to pick up changes.

[goals]
# Daily coding/work goal, in hours.
work_goal_hours = 4.0

[tracking]
# How often to poll the active window, in seconds.
poll_interval_seconds = 1.0
# Stop counting time toward the focused app after this many seconds without
# cursor movement (you stepped away, but the window is still focused).
idle_threshold_seconds = 180

# Any app class name containing one of these substrings (case-insensitive) is
# classified into that category. Title keywords below are checked first, so
# an app can still be reclassified based on what's open in it (e.g. a browser
# on a tutorial vs. a browser on Netflix).
[categories.apps]
work = ["code", "codium", "cursor", "nvim", "vim", "zed", "jetbrains", "pycharm", "intellij", "webstorm", "clion", "goland", "sublime_text", "kitty", "ghostty", "alacritty", "foot", "wezterm", "gnome-terminal", "konsole", "xterm", "org.gnome.terminal"]
communication = ["slack", "discord", "teams", "telegram", "signal", "thunderbird", "mail", "outlook"]
entertainment = ["spotify", "vlc", "mpv", "steam", "lutris", "plex"]
browsing = ["zen", "firefox", "chromium", "chrome", "brave", "google-chrome", "edge"]

# Any window title containing one of these substrings (case-insensitive)
# overrides the app-based category above.
[categories.title_keywords]
learning = ["tutorial", "course", "lecture", "how to", "crash course", "learn", "guide", "explained", "walkthrough", "udemy", "coursera", "khan academy", "freecodecamp", "edx", "pluralsight", "codecademy"]
watching = ["youtube", "netflix", "twitch", "hulu", "disney+", "disney plus", "prime video", "hbo", "plex", "crunchyroll", "funimation", "peacock", "paramount+", "anime", "watch online", "episode", "movie"]
communication = ["gmail", "whatsapp web", "outlook", "discord"]
"""


@dataclass
class Config:
    work_goal_seconds: float = 4 * 3600
    poll_interval_seconds: float = 1.0
    idle_threshold_seconds: float = 180.0
    work_apps: list[str] = field(default_factory=list)
    communication_apps: list[str] = field(default_factory=list)
    entertainment_apps: list[str] = field(default_factory=list)
    browser_apps: list[str] = field(default_factory=list)
    learning_keywords: list[str] = field(default_factory=list)
    streaming_keywords: list[str] = field(default_factory=list)
    communication_keywords: list[str] = field(default_factory=list)


def load_config() -> Config:
    if not CONFIG_PATH.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(DEFAULT_CONFIG_TOML)

    with CONFIG_PATH.open("rb") as f:
        data = tomllib.load(f)

    goals = data.get("goals", {})
    tracking = data.get("tracking", {})
    categories = data.get("categories", {})
    apps = categories.get("apps", {})
    keywords = categories.get("title_keywords", {})

    return Config(
        work_goal_seconds=float(goals.get("work_goal_hours", 4.0)) * 3600,
        poll_interval_seconds=float(tracking.get("poll_interval_seconds", 1.0)),
        idle_threshold_seconds=float(tracking.get("idle_threshold_seconds", 180.0)),
        work_apps=apps.get("work", []),
        communication_apps=apps.get("communication", []),
        entertainment_apps=apps.get("entertainment", []),
        browser_apps=apps.get("browsing", []),
        learning_keywords=keywords.get("learning", []),
        streaming_keywords=keywords.get("watching", []),
        communication_keywords=keywords.get("communication", []),
    )


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config()
    return _config
