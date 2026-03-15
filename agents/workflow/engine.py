"""
GhostOps Workflow Engine
=========================
Record/replay desktop workflows using Gemini 2.5 Flash for step extraction.

Recording:
  - Captures screenshot every 2s into memory
  - Stores user voice transcription alongside
  - start_recording() / stop_and_save(name)

Step extraction:
  - Sends screenshots + transcription to Gemini 2.5 Flash
  - Returns JSON array of steps

Replay:
  - For each step: screenshot → Gemini finds element → execute → verify

Storage:
  - Workflows saved to Firestore: workflows/{name}
  - Also cached locally in memory
"""

import asyncio
import json
import os
import time
from typing import Any

# [GEMINI] from google import genai
# [GEMINI] from google.genai import types
from dotenv import load_dotenv
# [GROQ]
from core.groq_provider import generate_vision

from desktop import screen as _screen

load_dotenv()

# ── Recording state ───────────────────────────────────────────────────────────
_recording: bool = False
_record_frames: list[dict] = []  # [{timestamp, raw_jpeg, transcription}]
_pending_transcription: str = ""
_record_task: asyncio.Task | None = None

# ── Firestore workflows cache ─────────────────────────────────────────────────
_workflow_cache: dict[str, list[dict]] = {}


def start_recording() -> None:
    """Begin recording screenshots and transcriptions."""
    global _recording, _record_frames, _pending_transcription
    _recording = True
    _record_frames = []
    _pending_transcription = ""
    print("[workflow] recording started")
    _ensure_record_loop()


def on_transcription(text: str) -> None:
    """Called when Live API returns user transcription. Appended to current frame."""
    global _pending_transcription
    if _recording:
        _pending_transcription += " " + text.strip()


def on_audio_chunk(data: bytes) -> None:
    """No-op for now — transcription is handled via on_transcription."""
    pass


async def _record_loop() -> None:
    """Background task: capture screenshot every 2s while recording."""
    global _record_frames, _pending_transcription
    while _recording:
        try:
            raw = await asyncio.to_thread(_screen._capture_raw)
            frame = {
                "timestamp": time.time(),
                "raw_jpeg": raw,
                "transcription": _pending_transcription.strip(),
            }
            _record_frames.append(frame)
            _pending_transcription = ""
            print(f"[workflow] captured frame {len(_record_frames)}")
        except Exception as exc:
            print(f"[workflow] capture error: {exc}")
        await asyncio.sleep(2.0)


def _ensure_record_loop() -> None:
    """Start the background record loop if not already running."""
    global _record_task
    if _record_task is None or _record_task.done():
        try:
            loop = asyncio.get_running_loop()
            _record_task = loop.create_task(_record_loop())
        except RuntimeError:
            pass


async def stop_and_save(name: str, session_id: str) -> list[dict]:
    """
    Stop recording, extract steps via Gemini, save to Firestore.
    Returns the extracted steps list.
    """
    global _recording, _record_task
    _recording = False
    if _record_task and not _record_task.done():
        _record_task.cancel()
    
    frames = list(_record_frames)
    # Flush any pending transcription into the last frame
    if _pending_transcription.strip() and frames:
        frames[-1]["transcription"] = (frames[-1]["transcription"] + " " + _pending_transcription).strip()
    print(f"[workflow] stopped. {len(frames)} frames captured")

    if not frames:
        return []

    steps = await _extract_steps(frames)
    await _save_workflow(name, steps, session_id)
    _workflow_cache[name] = steps
    print(f"[workflow] saved '{name}' with {len(steps)} steps")
    return steps


async def _extract_steps(frames: list[dict]) -> list[dict]:
    """Send frames + transcription to Groq vision for step extraction."""
    # Build transcription timeline
    narration = " ".join(f["transcription"] for f in frames if f.get("transcription")).strip()

    prompt = (
        "The user performed a workflow. Here are screenshots taken every 2 seconds "
        f"({len(frames)} frames total).\n\n"
        f"User narration: {narration or '(no narration)'}\n\n"
        "Extract the workflow as a JSON array of steps. Each step:\n"
        '{"step_number": 1, "action": "click|type|open|press|navigate", '
        '"target_description": "describe what to click/interact with", '
        '"value_if_any": "text to type or key to press, or empty string"}\n\n'
        "Return ONLY the JSON array, no markdown, no explanation."
    )

    # [GEMINI] client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    # [GEMINI] parts = [types.Part(text=prompt)]
    # [GEMINI] sample_frames = frames[::max(1, len(frames) // 10)][:10]
    # [GEMINI] for frame in sample_frames:
    # [GEMINI]     parts.append(types.Part(inline_data=types.Blob(data=frame["raw_jpeg"], mime_type="image/jpeg")))
    # [GEMINI] response = await client.aio.models.generate_content(model="gemini-2.5-flash", ...)

    # [GROQ] Use only the last frame as the reference screenshot for step extraction
    last_frame = frames[-1]["raw_jpeg"]
    try:
        raw = await generate_vision(prompt=prompt, image_bytes=last_frame, max_tokens=4096)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        steps = json.loads(raw)
        if not isinstance(steps, list):
            steps = []
        return steps
    except Exception as exc:
        print(f"[workflow] step extraction failed: {exc}")
        return []


async def _save_workflow(name: str, steps: list[dict], session_id: str) -> None:
    """Save workflow to Firestore."""
    try:
        from google.cloud import firestore
        db = firestore.AsyncClient(project=os.environ["GOOGLE_CLOUD_PROJECT"])
        await db.collection("workflows").document(name).set({
            "name": name,
            "session_id": session_id,
            "steps": steps,
            "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        })
        print(f"[workflow] saved to Firestore: {name}")
    except Exception as exc:
        print(f"[workflow] Firestore save failed (using local cache only): {exc}")


async def _load_workflow(name: str) -> list[dict]:
    """Load workflow from Firestore or local cache."""
    if name in _workflow_cache:
        return _workflow_cache[name]
    try:
        from google.cloud import firestore
        db = firestore.AsyncClient(project=os.environ["GOOGLE_CLOUD_PROJECT"])
        doc = await db.collection("workflows").document(name).get()
        if doc.exists:
            data = doc.to_dict()
            steps = data.get("steps", [])
            _workflow_cache[name] = steps
            return steps
    except Exception as exc:
        print(f"[workflow] Firestore load failed: {exc}")
    return []


async def replay(name: str, session_id: str) -> str:
    """
    Replay a workflow by name.
    For each step: screenshot → Gemini finds element → execute CUA action → verify.
    """
    steps = await _load_workflow(name)
    if not steps:
        return f"Workflow '{name}' not found or has no steps."

    print(f"[workflow] replaying '{name}': {len(steps)} steps")
    # [GEMINI] client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    completed = 0

    for step in steps:
        step_num = step.get("step_number", completed + 1)
        action = step.get("action", "")
        target = step.get("target_description", "")
        value = step.get("value_if_any", "")

        print(f"[workflow] step {step_num}: {action} on '{target}'")

        try:
            # 1. Take screenshot
            raw = await asyncio.to_thread(_screen._capture_raw)

            # 2. Find element coordinates (for click/type actions)
            if action in ("click", "type") and target:
                # [GEMINI] coord_parts = [types.Part(text=...), types.Part(inline_data=...)]
                # [GEMINI] coord_resp = await client.aio.models.generate_content(...)
                # [GROQ]
                coord_prompt = (
                    f"Find the element described as '{target}' in this screenshot.\n"
                    "Return ONLY a JSON object: {\"x\": <int>, \"y\": <int>} "
                    "in 1280x720 coordinate space. No markdown, no explanation."
                )
                coord_json = await generate_vision(
                    prompt=coord_prompt, image_bytes=raw, max_tokens=100
                )
                coord_json = coord_json.strip()
                if coord_json.startswith("```"):
                    coord_json = coord_json.split("```")[1].lstrip("json")
                coords = json.loads(coord_json)
                x, y = int(coords.get("x", 640)), int(coords.get("y", 360))

                import pyautogui
                sw, sh = pyautogui.size()
                ax, ay = int(x * sw / 1280), int(y * sh / 720)

                if action == "click":
                    await asyncio.to_thread(pyautogui.click, ax, ay)
                elif action == "type" and value:
                    import subprocess
                    await asyncio.to_thread(
                        subprocess.run, ["pbcopy"], input=value.encode(), capture_output=True
                    )
                    await asyncio.sleep(0.1)
                    await asyncio.to_thread(pyautogui.hotkey, "command", "v")

            elif action == "open" and value:
                import subprocess
                await asyncio.to_thread(
                    subprocess.run, ["open", "-a", value], capture_output=True
                )
            elif action in ("press", "key") and value:
                import pyautogui
                parts_key = [p.strip() for p in value.split("+")]
                if len(parts_key) == 1:
                    await asyncio.to_thread(pyautogui.press, parts_key[0])
                else:
                    await asyncio.to_thread(pyautogui.hotkey, *parts_key)
            elif action == "navigate" and value:
                # Open URL in default browser
                import subprocess
                await asyncio.to_thread(subprocess.run, ["open", value], capture_output=True)

            completed += 1
            await asyncio.sleep(0.5)

        except Exception as exc:
            print(f"[workflow] step {step_num} failed: {exc}")
            return f"Workflow '{name}' stopped at step {step_num}: {exc}"

    return f"Workflow '{name}' completed: {completed}/{len(steps)} steps."
