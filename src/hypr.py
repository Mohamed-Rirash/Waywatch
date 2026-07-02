from __future__ import annotations

import asyncio
import json


async def get_active_window() -> tuple[str, str] | None:
    """Return (app_class, title) for the focused Hyprland window, or None if nothing is focused."""
    proc = await asyncio.create_subprocess_exec(
        "hyprctl",
        "-j",
        "activewindow",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0 or not stdout:
        return None

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return None

    if not data or "class" not in data:
        return None

    return data.get("class") or "unknown", data.get("title") or ""
