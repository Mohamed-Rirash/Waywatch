import pytest

from src import categories
from src.config import Config


@pytest.fixture
def config():
    return Config(
        work_goal_seconds=4 * 3600,
        poll_interval_seconds=1.0,
        idle_threshold_seconds=180.0,
        work_apps=["code", "kitty", "ghostty"],
        communication_apps=["slack", "discord"],
        entertainment_apps=["spotify", "vlc"],
        browser_apps=["zen", "firefox"],
        learning_keywords=["tutorial", "course", "crash course", "learn"],
        streaming_keywords=["youtube", "netflix", "anime", "watch online"],
        communication_keywords=["gmail"],
    )


@pytest.fixture(autouse=True)
def patch_config(monkeypatch, config):
    monkeypatch.setattr(categories, "get_config", lambda: config)


def test_work_app_is_work():
    assert categories.categorize("code", "app.py - Visual Studio Code") == "Work"


def test_terminal_app_matches_via_substring():
    assert categories.categorize("com.mitchellh.ghostty", "~/projects") == "Work"


def test_learning_keyword_overrides_generic_browsing():
    assert categories.categorize("zen", "Python Asyncio Tutorial — Zen Browser") == "Learning"


def test_streaming_keyword_is_watching():
    assert categories.categorize("zen", "Some Anime - Watch Online — Zen Browser") == "Watching"


def test_learning_takes_priority_over_streaming_platform():
    """A tutorial hosted on YouTube should read as Learning, not Watching."""
    assert categories.categorize("zen", "React Crash Course - YouTube") == "Learning"


def test_generic_browsing_falls_back_to_browsing():
    assert categories.categorize("zen", "GitHub - some/repo — Zen Browser") == "Browsing"


def test_communication_app_is_communication():
    assert categories.categorize("slack", "#general — Slack") == "Communication"


def test_communication_keyword_in_browser_overrides_browsing():
    assert categories.categorize("zen", "Inbox — Gmail — Zen Browser") == "Communication"


def test_entertainment_app_is_entertainment():
    assert categories.categorize("spotify", "Now Playing") == "Entertainment"


def test_unrecognized_app_is_other():
    assert categories.categorize("some-random-app", "random title") == "Other"


def test_empty_app_and_title_is_other():
    assert categories.categorize("", "") == "Other"


def test_matching_is_case_insensitive():
    assert categories.categorize("CODE", "SOME TUTORIAL TITLE") == "Learning"
