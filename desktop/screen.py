"""
Background screenshot capture.

Runs as an asyncio Task (asyncio.to_thread wraps the blocking mss call).
Stores latest raw JPEG bytes in module-level `cached_screenshot_raw`.
Sends each frame to Gemini Live API via `screen_and_video_loop` in main.py.

Usage:
    from desktop import screen as _screen
    raw = await asyncio.to_thread(_screen._capture_raw)
"""

import asyncio
import io

# cached_screenshot_raw: raw JPEG bytes, None until first capture
cached_screenshot_raw: bytes | None = None

# How often to refresh the screenshot (seconds)
CAPTURE_INTERVAL = 5


def _capture_raw() -> bytes:
    """
    Synchronous screenshot capture. Called via asyncio.to_thread().
    Returns raw JPEG bytes at 1280×720 max resolution.
    JPEG quality=60 keeps it ~50-100KB — fast to stream to Live API.
    """
    # Late import so the desktop module doesn't require mss/Pillow on the backend
    import mss
    from PIL import Image

    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary monitor
        shot = sct.grab(monitor)
        # Convert mss BGRA → RGB Pillow Image
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        # Resize to 1280×720 — matches coordinate space used for click_at tool
        img.thumbnail((1280, 720), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=60)
        return buf.getvalue()
