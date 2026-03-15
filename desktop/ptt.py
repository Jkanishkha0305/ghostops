"""
GhostOps Push-to-Talk (PTT)
============================
Reliable multi-turn voice agent using standard generate_content API.
No Live API, no WebSocket, no VAD — press ENTER to talk, ENTER to send.

Each turn sends to Gemini:
  - Your recorded audio (WAV, 16kHz mono)
  - Current screenshot (JPEG, for computer use context)
  - Text conversation history (last 12 turns, no bulky audio/images)
  - System prompt + Firestore memory from previous sessions

Computer use: click_at, type_text, open_app, press_key
TTS: macOS `say -v Samantha`

Run:
  uv run python -m desktop.ptt
"""

import asyncio
import io
import os
import subprocess
import sys
import threading
import uuid
import wave

import pyaudio
import pyautogui
from dotenv import load_dotenv
from google import genai
from google.genai import types

from desktop import screen as _screen
from desktop.memory_client import load_memory, save_turn
from backend.memory import turns_to_context

load_dotenv()

FORMAT = pyaudio.paInt16
CHANNELS = 1
SAMPLE_RATE = 16_000
CHUNK = 1_024

MODEL = os.environ.get("PTT_MODEL", "gemini-2.5-flash")

# ── Tool declarations ─────────────────────────────────────────────────────────

CLICK_AT = types.FunctionDeclaration(
    name="click_at",
    description=(
        "Click at pixel coordinates on the screen. "
        "Screenshots are sent at 1280×720 resolution — use that coordinate space."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "x": types.Schema(type=types.Type.INTEGER, description="X coordinate (0–1280)"),
            "y": types.Schema(type=types.Type.INTEGER, description="Y coordinate (0–720)"),
            "button": types.Schema(
                type=types.Type.STRING,
                description="'left' (default), 'right', or 'double'",
            ),
        },
        required=["x", "y"],
    ),
)

TYPE_TEXT = types.FunctionDeclaration(
    name="type_text",
    description="Type text at the current cursor position.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={"text": types.Schema(type=types.Type.STRING)},
        required=["text"],
    ),
)

OPEN_APP = types.FunctionDeclaration(
    name="open_app",
    description="Open a macOS application by name. E.g. 'Safari', 'Terminal', 'VS Code'.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={"app_name": types.Schema(type=types.Type.STRING)},
        required=["app_name"],
    ),
)

PRESS_KEY = types.FunctionDeclaration(
    name="press_key",
    description="Press a key or hotkey. E.g. 'enter', 'escape', 'command+c', 'command+space'.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={"key": types.Schema(type=types.Type.STRING)},
        required=["key"],
    ),
)

_TOOLS = [types.Tool(function_declarations=[CLICK_AT, TYPE_TEXT, OPEN_APP, PRESS_KEY])]

# ── Recording ─────────────────────────────────────────────────────────────────

_stop_recording = threading.Event()


def _record_to_event() -> bytes:
    """
    Records PCM16 audio from mic until _stop_recording is set.
    Called via asyncio.to_thread() — blocks the thread, not the event loop.
    Returns raw PCM bytes (int16, 16 kHz, mono).
    """
    _stop_recording.clear()
    pya = pyaudio.PyAudio()
    stream = pya.open(
        format=FORMAT, channels=CHANNELS, rate=SAMPLE_RATE,
        input=True, frames_per_buffer=CHUNK,
    )
    frames: list[bytes] = []
    while not _stop_recording.is_set():
        try:
            frames.append(stream.read(CHUNK, exception_on_overflow=False))
        except OSError:
            break
    stream.stop_stream()
    stream.close()
    pya.terminate()
    return b"".join(frames)


def _pcm_to_wav(pcm: bytes) -> bytes:
    """Wrap raw PCM bytes in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)       # int16 = 2 bytes per sample
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    return buf.getvalue()


# ── TTS ───────────────────────────────────────────────────────────────────────

async def speak(text: str) -> None:
    """Speak text using macOS `say`. Waits for speech to finish."""
    proc = await asyncio.create_subprocess_exec("say", "-v", "Samantha", text)
    await proc.wait()


# ── Computer use ──────────────────────────────────────────────────────────────

def _scale(x: int, y: int) -> tuple[int, int]:
    """Scale 1280×720 screenshot coords to actual screen resolution."""
    w, h = pyautogui.size()
    return int(x * w / 1280), int(y * h / 720)


async def execute_tool(name: str, args: dict) -> str:
    """Execute a computer use tool. Returns a result string."""
    try:
        if name == "click_at":
            sx, sy = _scale(int(args["x"]), int(args["y"]))
            btn = args.get("button", "left")
            if btn == "double":
                await asyncio.to_thread(pyautogui.doubleClick, sx, sy)
            elif btn == "right":
                await asyncio.to_thread(pyautogui.rightClick, sx, sy)
            else:
                await asyncio.to_thread(pyautogui.click, sx, sy)
            print(f"  [cua] click({btn}) at screen ({sx}, {sy})")
            return f"Clicked ({args['x']}, {args['y']})"

        if name == "type_text":
            text = args["text"]
            r = await asyncio.to_thread(
                subprocess.run, ["pbcopy"], input=text.encode(), capture_output=True,
            )
            if r.returncode != 0:
                return f"pbcopy failed: {r.stderr.decode()}"
            await asyncio.sleep(0.1)
            await asyncio.to_thread(pyautogui.hotkey, "command", "v")
            print(f"  [cua] typed: {text[:60]}")
            return f"Typed: {text[:60]}{'...' if len(text) > 60 else ''}"

        if name == "open_app":
            app = args["app_name"]
            r = await asyncio.to_thread(
                subprocess.run, ["open", "-a", app], capture_output=True,
            )
            if r.returncode != 0:
                return f"Could not open {app}: {r.stderr.decode()}"
            print(f"  [cua] opened: {app}")
            return f"Opened {app}"

        if name == "press_key":
            key = args["key"]
            parts = [p.strip() for p in key.split("+")]
            if len(parts) == 1:
                await asyncio.to_thread(pyautogui.press, parts[0])
            else:
                await asyncio.to_thread(pyautogui.hotkey, *parts)
            print(f"  [cua] pressed: {key}")
            return f"Pressed {key}"

        return f"Unknown tool: {name}"

    except Exception as exc:  # noqa: BLE001
        print(f"  [cua] {name} error: {exc}")
        return f"Error executing {name}: {exc}"


# ── API turn ──────────────────────────────────────────────────────────────────

async def send_turn(
    client: genai.Client,
    history: list[types.Content],
    wav_bytes: bytes,
    jpeg_bytes: bytes | None,
    system_prompt: str,
) -> tuple[str, list[types.Content]]:
    """
    Send audio (+ optional screenshot) to Gemini with conversation history.
    Handles tool call loops automatically.

    History is text-only (no audio/image blobs) to keep it lightweight.
    Audio and screenshot are injected only into the current user turn.

    Returns (response_text, updated_text_history).

    Data flow:
      history (text) ──┐
      audio (wav)  ────┤──► generate_content ──► [tool loop] ──► text response
      screenshot   ────┘                                           │
                                                                   ▼
                                              history += [user=[voice], model=[text]]
    """
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=_TOOLS,
    )

    # Build current user parts: audio + (optional) screenshot
    current_parts: list[types.Part] = [
        types.Part(inline_data=types.Blob(data=wav_bytes, mime_type="audio/wav")),
    ]
    if jpeg_bytes:
        current_parts.append(
            types.Part(inline_data=types.Blob(data=jpeg_bytes, mime_type="image/jpeg"))
        )

    # Contents for API: text history + current audio/image user turn
    api_contents: list[types.Content] = list(history) + [
        types.Content(role="user", parts=current_parts)
    ]

    # Track tool call/response pairs added this turn (kept in history)
    tool_contents: list[types.Content] = []
    final_content: types.Content | None = None

    while True:
        response = await client.aio.models.generate_content(
            model=MODEL,
            contents=api_contents + tool_contents,
            config=config,
        )

        if not response.candidates:
            return "Sorry, I didn't get a response.", history

        content = response.candidates[0].content
        final_content = content

        fcs = [p.function_call for p in content.parts if p.function_call]
        if not fcs:
            break

        # Execute all tool calls in this response
        print(f"  [tool] {len(fcs)} call(s)...")
        tool_contents.append(content)  # model's function_call content
        tool_parts: list[types.Part] = []
        for fc in fcs:
            name = fc.name
            fc_args = dict(fc.args) if fc.args else {}
            print(f"  [tool] {name}({fc_args})")
            result = await execute_tool(name, fc_args)
            tool_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=name,
                        response={"result": result},
                    )
                )
            )
        tool_contents.append(types.Content(role="user", parts=tool_parts))

    # Extract final text
    text = "".join(p.text for p in final_content.parts if p.text).strip()

    # Build updated text-only history (no audio, no images from previous turns)
    new_history = list(history)
    new_history.append(
        types.Content(role="user", parts=[types.Part(text="[voice message]")])
    )
    new_history.extend(tool_contents)  # tool call/response pairs (if any)
    new_history.append(final_content)  # model's final text response

    # Keep history bounded — avoid unbounded growth over a long session
    MAX_HISTORY = 12  # ~6 exchanges
    if len(new_history) > MAX_HISTORY:
        new_history = new_history[-MAX_HISTORY:]

    return text, new_history


# ── System prompt ─────────────────────────────────────────────────────────────

def build_system_prompt(memory_context: str) -> str:
    base = (
        "You are GhostOps, an AI desktop agent with persistent memory. "
        "You can see the user's screen in each message (screenshot included). "
        "You can act on their Mac using click_at, type_text, open_app, press_key. "
        "Always confirm before destructive actions (delete, send, submit). "
        "Keep responses concise and conversational — this is a voice interface. "
        "Screenshot coordinates: 1280×720 pixels.\n\n"
    )
    if memory_context:
        base += memory_context + "\n\n"
    return base


# ── Main loop ─────────────────────────────────────────────────────────────────

async def run() -> None:
    if not os.environ.get("GEMINI_API_KEY"):
        print("Missing GEMINI_API_KEY — add it to .env")
        sys.exit(1)

    session_id = os.environ.get("FIRESTORE_SESSION_ID", f"ptt-{uuid.uuid4().hex[:8]}")
    print(f"[ptt] session_id={session_id}")

    # Load Firestore memory
    cloud_run_url = os.environ.get("CLOUD_RUN_URL")
    if cloud_run_url:
        print("[ptt] loading memory from Firestore...")
        memory_turns = await load_memory(session_id=session_id, limit=10)
        print(f"[ptt] loaded {len(memory_turns)} memory turn(s)")
        memory_context = turns_to_context(memory_turns)
    else:
        print("[ptt] CLOUD_RUN_URL not set — starting without memory")
        memory_context = ""

    system_prompt = build_system_prompt(memory_context)
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    history: list[types.Content] = []
    _bg_tasks: set = set()

    print(f"\nGhostOps PTT ready (model: {MODEL}).")
    print("Press ENTER to start recording, ENTER again to send.")
    print("Ctrl+C to quit.\n")

    while True:
        try:
            # ── Wait for user to start recording ──────────────────────────────
            await asyncio.to_thread(input, "[ ENTER to record ] ")
            print("  Recording... press ENTER to send.", end="", flush=True)

            # ── Record in background, wait for stop signal ────────────────────
            record_task = asyncio.create_task(asyncio.to_thread(_record_to_event))
            await asyncio.to_thread(input, "")  # ENTER to stop
            _stop_recording.set()
            pcm = await record_task

            duration_s = len(pcm) / (SAMPLE_RATE * 2)
            if duration_s < 0.3:
                print("  (too short, ignored)")
                continue

            print(f"\n  Recorded {duration_s:.1f}s → encoding...")
            wav_bytes = _pcm_to_wav(pcm)

            # ── Capture screenshot ────────────────────────────────────────────
            try:
                jpeg_bytes = await asyncio.to_thread(_screen._capture_raw)
            except Exception as exc:  # noqa: BLE001
                print(f"  [screen] capture failed: {exc}")
                jpeg_bytes = None

            # ── Send to Gemini ────────────────────────────────────────────────
            print("  Thinking...", end="", flush=True)
            text, history = await send_turn(
                client, history, wav_bytes, jpeg_bytes, system_prompt
            )
            print(f"\r  ", end="")  # clear "Thinking..."

            if not text:
                print("  [no response text]")
                continue

            print(f"\nGhostOps: {text}\n")

            # ── Speak response ────────────────────────────────────────────────
            await speak(text)

            # ── Save to Firestore (fire-and-forget) ───────────────────────────
            if cloud_run_url:
                t = asyncio.create_task(
                    save_turn(session_id=session_id, role="model", text=text)
                )
                _bg_tasks.add(t)
                t.add_done_callback(_bg_tasks.discard)

        except KeyboardInterrupt:
            print("\n[ptt] bye!")
            break
        except Exception as exc:  # noqa: BLE001
            print(f"\n[ptt] error: {type(exc).__name__}: {exc}")
            # Continue loop — don't crash on API errors


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
