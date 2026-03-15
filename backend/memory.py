"""
Firestore memory: read recent turns, write new turns.

Schema:
  sessions/{session_id}/turns (subcollection)
    document fields: role, text, screen_summary, timestamp (ISO string)

Load on startup → inject into system prompt.
Write after each turn → fire-and-forget (caller does not await).
"""

import os
from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore

_db: firestore.AsyncClient | None = None


def _reset_db() -> None:
    global _db
    _db = None


def _get_db() -> firestore.AsyncClient:
    global _db
    if _db is None:
        _db = firestore.AsyncClient(project=os.environ["GOOGLE_CLOUD_PROJECT"])
    return _db


async def load_memory(session_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """
    Returns the most recent `limit` turns for this session, oldest first.
    Returns [] if no prior session exists (fresh start — no greeting fires).
    """
    db = _get_db()
    turns_ref = (
        db.collection("sessions")
        .document(session_id)
        .collection("turns")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    docs = await turns_ref.get()
    turns = [doc.to_dict() for doc in reversed(docs)]  # oldest first
    return turns


async def save_turn(session_id: str, turn: dict[str, Any]) -> None:
    """
    Appends one turn to Firestore. Called fire-and-forget — do not await
    from the audio loop; wrap in asyncio.create_task() instead.
    """
    db = _get_db()
    doc = {**turn, "timestamp": datetime.now(timezone.utc).isoformat()}
    await (
        db.collection("sessions")
        .document(session_id)
        .collection("turns")
        .add(doc)
    )


def turns_to_context(turns: list[dict[str, Any]]) -> str:
    """
    Formats memory turns into a concise string for the system prompt.
    Keeps it under ~500 tokens — enough context without blowing the prompt.
    """
    if not turns:
        return ""
    lines = ["[MEMORY — recent sessions]"]
    for t in turns[-5:]:  # last 5 turns only
        role = t.get("role", "user")
        text = t.get("text", "")[:120]  # truncate long turns
        screen = t.get("screen_summary", "")[:80]
        lines.append(f"  [{role}] {text} (screen: {screen})")
    return "\n".join(lines)
