from __future__ import annotations

import asyncio
import json


async def get_cursor_pos() -> tuple[int, int] | None:
    """Return the current (x, y) cursor position, or None if it can't be read.

    Hyprland doesn't expose an idle timer over hyprctl, so cursor movement is used
    as a lightweight proxy for "the user is still here" — if the cursor hasn't
    moved in a while, the focused window is likely just sitting there unattended.
    """
    proc = await asyncio.create_subprocess_exec(
        "hyprctl",
        "-j",
        "cursorpos",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0 or not stdout:
        return None

    try:
        data = json.loads(stdout)
        return data["x"], data["y"]
    except (json.JSONDecodeError, KeyError):
        return None
