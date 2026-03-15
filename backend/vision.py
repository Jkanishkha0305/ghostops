"""
Screen vision: send a screenshot (base64 JPEG) to Gemini Flash,
get back a plain-English description of what's on screen.

Called by the /vision endpoint on Cloud Run when the desktop's
get_screen_context() tool fires during a Live API session.
"""

import os
import base64

from google import genai
from google.genai import types

_client: genai.Client | None = None

VISION_MODEL = "gemini-2.0-flash-001"

VISION_PROMPT = (
    "Describe what is currently visible on this screen in 2-3 short sentences. "
    "Focus on: what application is open, what content is visible, "
    "and any key text (PR titles, file names, error messages). "
    "Be specific and factual. Do not include opinions or suggestions."
)


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


async def describe_screenshot(screenshot_b64: str) -> str:
    """
    Sends screenshot to Gemini Flash, returns plain-English screen description.
    Returns "screen not available" on any failure — never raises.
    """
    if not screenshot_b64:
        return "screen not available"
    try:
        client = _get_client()
        image_bytes = base64.b64decode(screenshot_b64)
        response = await client.aio.models.generate_content(
            model=VISION_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                types.Part.from_text(text=VISION_PROMPT),
            ],
        )
        return response.text.strip() if response.text else "screen not available"
    except Exception as exc:  # noqa: BLE001
        # Log but never crash the voice session
        print(f"[vision] describe_screenshot failed: {exc}")
        return "screen not available"
