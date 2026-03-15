"""
GhostOps integration tests — hit real APIs.

Run all:    pytest tests/ -v
Run offline: pytest tests/ -v -m "not integration"

Requires: .env with GEMINI_API_KEY, GOOGLE_CLOUD_PROJECT, CLOUD_RUN_URL
"""

import asyncio
import base64
import os
import uuid

import pytest
from dotenv import load_dotenv

load_dotenv()

TEST_SESSION = f"test-{uuid.uuid4().hex[:8]}"


# ── 1. Firestore roundtrip ───────────────────────────────────────────────────

@pytest.mark.integration
async def test_memory_roundtrip():
    """Write a turn, read it back, verify structure."""
    from backend.memory import save_turn, load_memory

    turn = {"role": "user", "text": "hello from test", "screen_summary": "test screen"}
    await save_turn(TEST_SESSION, turn)

    turns = await load_memory(TEST_SESSION, limit=5)
    assert len(turns) >= 1
    texts = [t.get("text") for t in turns]
    assert "hello from test" in texts


# ── 2. Gemini Flash screen summary ──────────────────────────────────────────

@pytest.mark.integration
async def test_screen_summary_returns_text():
    """
    Send a tiny 1x1 red JPEG to Gemini Flash.
    Expect a non-empty string back (content doesn't matter, just that it works).
    """
    from backend.vision import describe_screenshot

    # Minimal valid JPEG (1x1 red pixel)
    tiny_jpg_b64 = (
        "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkS"
        "Ew8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJ"
        "CQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIy"
        "MjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFgABAQEAAAAAAAAA"
        "AAAAAAAABgUH/8QAHhAAAQMFAQAAAAAAAAAAAAAAAQACAwQFERIx/8QAFAEBAAAA"
        "AAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8A"
        "nWtNUo2p0WmlpqH6EbCiQAf/2Q=="
    )
    result = await describe_screenshot(tiny_jpg_b64)
    assert isinstance(result, str)
    assert len(result) > 0


# ── 3. Cloud Run /health ─────────────────────────────────────────────────────

@pytest.mark.integration
async def test_cloud_run_health():
    """Verify Cloud Run backend is up and /health returns 200."""
    import httpx

    url = os.environ.get("CLOUD_RUN_URL", "http://localhost:8080")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{url}/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── 4. Memory loads on startup ───────────────────────────────────────────────

@pytest.mark.integration
async def test_memory_loads_and_formats():
    """
    Seed 3 turns, load them, verify turns_to_context produces a non-empty string
    when memory exists and empty string when it doesn't.
    """
    from backend.memory import save_turn, load_memory, turns_to_context

    sid = f"test-ctx-{uuid.uuid4().hex[:6]}"
    for i in range(3):
        await save_turn(sid, {"role": "user", "text": f"turn {i}", "screen_summary": f"screen {i}"})

    turns = await load_memory(sid, limit=10)
    assert len(turns) == 3

    ctx = turns_to_context(turns)
    assert "[MEMORY" in ctx
    assert "turn" in ctx

    # Empty session → empty context
    empty_ctx = turns_to_context([])
    assert empty_ctx == ""


# ── 5. Startup greeting fires when memory exists ─────────────────────────────

@pytest.mark.integration
async def test_startup_greeting_context_injected():
    """
    Verify that when memory turns exist, build_system_prompt includes [MEMORY].
    (Tests the prompt-building logic without hitting Live API.)
    """
    from desktop.main import build_system_prompt
    from backend.memory import turns_to_context

    turns = [
        {"role": "user", "text": "check my PRs", "screen_summary": "GitHub PR page"},
    ]
    ctx = turns_to_context(turns)
    prompt = build_system_prompt(ctx)

    assert "[MEMORY" in prompt
    assert "GitHub PR page" in prompt


# ── 6. Startup greeting skips when no memory ────────────────────────────────

async def test_startup_greeting_skips_on_empty_memory():
    """
    No integration needed — pure logic test.
    Verifies build_system_prompt with empty context has no [MEMORY] block.
    """
    from desktop.main import build_system_prompt

    prompt = build_system_prompt("")
    assert "[MEMORY" not in prompt
    assert "GhostOps" in prompt
