"""
HTTP client for GhostOps Cloud Run backend.

Wraps /memory (write) and /memory/{id} (read).
Vision is now handled natively by Gemini Live API (realtimeInput.video) —
the /vision endpoint is no longer used by the desktop client.
All calls use httpx async with a 6-second timeout.
Failures return safe fallbacks — never crash the voice session.
"""

import os
from typing import Any

import httpx

_TIMEOUT = httpx.Timeout(6.0)


def _base_url() -> str:
    url = os.environ.get("CLOUD_RUN_URL", "http://localhost:8080")
    return url.rstrip("/")


async def get_screen_summary(screenshot_b64: str | None) -> str:
    """
    Sends screenshot to Cloud Run /vision, returns plain-English description.
    Returns "screen not available" on any failure.
    """
    if not screenshot_b64:
        return "screen not available"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_base_url()}/vision",
                json={"screenshot_b64": screenshot_b64},
            )
            resp.raise_for_status()
            return resp.json().get("screen_summary", "screen not available")
    except Exception as exc:  # noqa: BLE001
        print(f"[memory_client] get_screen_summary failed: {exc}")
        return "screen not available"


async def load_memory(session_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Loads recent turns from Cloud Run /memory/{session_id}.
    Returns [] on failure — triggers a silent fresh start.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_base_url()}/memory/{session_id}",
                params={"limit": limit},
            )
            resp.raise_for_status()
            return resp.json().get("turns", [])
    except Exception as exc:  # noqa: BLE001
        print(f"[memory_client] load_memory failed: {exc}")
        return []


async def save_turn(
    session_id: str,
    role: str,
    text: str,
    screen_summary: str = "",
) -> None:
    """
    Saves one turn to Firestore via Cloud Run /memory.
    Fire-and-forget — caller wraps in asyncio.create_task().
    Failures are logged but never raised.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            await client.post(
                f"{_base_url()}/memory",
                json={
                    "session_id": session_id,
                    "role": role,
                    "text": text,
                    "screen_summary": screen_summary,
                },
            )
    except Exception as exc:  # noqa: BLE001
        print(f"[memory_client] save_turn failed: {exc}")
