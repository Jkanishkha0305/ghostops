"""
GhostOps Cloud Run backend — FastAPI service.

Endpoints:
  POST /vision   — screenshot → Gemini Flash → screen_summary
  POST /memory   — save a turn to Firestore
  GET  /memory   — load recent turns from Firestore
  GET  /health   — liveness check (used in deploy verification + demo proof)

All endpoints are unauthenticated for hackathon demo.
Add Bearer token auth in v2 (see TODOS.md).
"""

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.vision import describe_screenshot
from backend.memory import load_memory, save_turn

load_dotenv()

app = FastAPI(title="GhostOps Backend", version="1.0.0")


# ── Request / Response models ────────────────────────────────────────────────

class VisionRequest(BaseModel):
    screenshot_b64: str  # base64-encoded JPEG


class VisionResponse(BaseModel):
    screen_summary: str


class MemoryWriteRequest(BaseModel):
    session_id: str
    role: str           # "user" or "model"
    text: str
    screen_summary: str = ""


class MemoryReadResponse(BaseModel):
    turns: list[dict[str, Any]]


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check. Screenshot for GCP console proof of deployment."""
    return {"status": "ok", "service": "ghostops-backend"}


@app.post("/vision", response_model=VisionResponse)
async def vision(req: VisionRequest) -> VisionResponse:
    """
    Accepts a base64 JPEG screenshot, returns a plain-English screen description.
    Called by the desktop's get_screen_context() tool handler.
    """
    if not req.screenshot_b64:
        raise HTTPException(status_code=400, detail="screenshot_b64 is required")
    summary = await describe_screenshot(req.screenshot_b64)
    return VisionResponse(screen_summary=summary)


@app.post("/memory")
async def memory_write(req: MemoryWriteRequest) -> dict[str, str]:
    """
    Saves one conversation turn to Firestore.
    Fire-and-forget from the desktop — failures are logged, not raised.
    """
    try:
        await save_turn(
            session_id=req.session_id,
            turn={
                "role": req.role,
                "text": req.text,
                "screen_summary": req.screen_summary,
            },
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[memory] save_turn failed: {exc}")
    return {"status": "saved"}


@app.get("/memory/{session_id}", response_model=MemoryReadResponse)
async def memory_read(session_id: str, limit: int = 10) -> MemoryReadResponse:
    """
    Returns the most recent `limit` turns for a session.
    Called once at desktop startup to load context.
    """
    turns = await load_memory(session_id=session_id, limit=limit)
    return MemoryReadResponse(turns=turns)


# ── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)
