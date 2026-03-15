"""
GhostOps Desktop Client
=======================
Connects to Gemini Live API for real-time voice conversation.
The agent can see your screen on demand (get_screen_context tool → realtimeInput.video)
and act on it (click, type, open apps, press keys via pyautogui).
Remembers context across sessions (Firestore via Cloud Run).

Architecture:
  mic → audio_in_queue ──────────────────────────────────────┐
                                                              ▼
  get_screen_context tool call ──► capture JPEG              Gemini Live API
        ↓ send_realtime_input(video=JPEG)  ─────────────────┘  │
        ↓ send_tool_response("frame sent") ──────────────────┘  ▼
                                                          audio_out_queue → speaker
  Computer use tools: click_at / type_text / open_app / press_key
        ↓ pyautogui / subprocess                               │
        ↓ post-action screenshot → realtimeInput.video     save_turn() fire-and-forget
                                                               ↓
                                                          Cloud Run /memory → Firestore

WHY no continuous video stream:
  Sending realtimeInput.video while the model is speaking causes an `interrupted` event.
  The model processes the frame, has no new user speech to respond to, and goes silent.
  On-demand screen capture (via tool call) avoids this — video only arrives when the
  model has explicitly requested context, never mid-response.

Audio fix: NO send_client_content greeting trigger.
  System prompt handles greeting naturally on first speech.
  Mixing clientContent with realtimeInput audio breaks the session.

Run:
  python -m desktop.main
"""

import asyncio
import base64
import os
import subprocess
import sys
import threading
import uuid

import pyaudio
import pyautogui
from dotenv import load_dotenv
from google import genai
from google.genai import types

from desktop.memory_client import get_screen_summary, load_memory, save_turn
from desktop import screen as _screen
from backend.memory import turns_to_context

load_dotenv()

# Disable pyautogui failsafe only if explicitly requested
# Default: FAILSAFE=True (move mouse to corner to stop the agent — safety net)
# pyautogui.FAILSAFE = False

# ── Audio constants ──────────────────────────────────────────────────────────
FORMAT           = pyaudio.paInt16
CHANNELS         = 1
SEND_SAMPLE_RATE = 16_000   # mic → Live API
RECV_SAMPLE_RATE = 24_000   # Live API → speaker
CHUNK_SIZE       = 1_024    # ~64ms at 16kHz

LIVE_MODEL = "gemini-2.5-flash-native-audio-latest"

# ── Tool declarations ─────────────────────────────────────────────────────────
GET_SCREEN_CONTEXT = types.FunctionDeclaration(
    name="get_screen_context",
    description=(
        "Captures and returns a live screenshot of the user's screen. "
        "Call this when the user asks about their screen, references something visible, "
        "or when screen context would help answer their question or plan a computer use action."
    ),
    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
)

# ── Computer use tool declarations ───────────────────────────────────────────
CLICK_AT = types.FunctionDeclaration(
    name="click_at",
    description=(
        "Click at pixel coordinates on the screen. "
        "Screenshots are sent at 1280×720 resolution — use that coordinate space. "
        "Identify the target element from the latest screenshot before clicking."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "x": types.Schema(type=types.Type.INTEGER, description="X coordinate (0–1280)"),
            "y": types.Schema(type=types.Type.INTEGER, description="Y coordinate (0–720)"),
            "button": types.Schema(
                type=types.Type.STRING,
                description="Mouse button: 'left' (default), 'right', or 'double'",
            ),
        },
        required=["x", "y"],
    ),
)

TYPE_TEXT = types.FunctionDeclaration(
    name="type_text",
    description=(
        "Type text at the current cursor position. "
        "Call click_at on a text field first if the cursor is not already there."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "text": types.Schema(type=types.Type.STRING, description="Text to type"),
        },
        required=["text"],
    ),
)

OPEN_APP = types.FunctionDeclaration(
    name="open_app",
    description=(
        "Open a macOS application by name. "
        "Examples: 'Safari', 'Mail', 'VS Code', 'Terminal', 'Finder', 'Spotify', 'Calendar'."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "app_name": types.Schema(type=types.Type.STRING, description="Application name"),
        },
        required=["app_name"],
    ),
)

PRESS_KEY = types.FunctionDeclaration(
    name="press_key",
    description=(
        "Press a keyboard key or hotkey combination. "
        "Examples: 'enter', 'escape', 'tab', 'delete', "
        "'command+c', 'command+v', 'command+space', 'command+tab', 'command+w'."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "key": types.Schema(
                type=types.Type.STRING,
                description="Key name or combo, e.g. 'enter', 'command+c'",
            ),
        },
        required=["key"],
    ),
)

# ── State shared across coroutines ───────────────────────────────────────────
audio_in_queue:  asyncio.Queue[bytes] = asyncio.Queue()
audio_out_queue: asyncio.Queue[bytes | None] = asyncio.Queue()


def build_system_prompt(memory_context: str) -> str:
    base = (
        "You are GhostOps, an AI desktop agent with persistent memory and on-demand screen vision. "
        "Use get_screen_context to see the user's screen whenever it would help. "
        "You can act on the user's Mac using: click_at, type_text, open_app, press_key. "
        "Always call get_screen_context before using click_at so you know what's on screen. "
        "For destructive actions (delete, send, submit), confirm with the user first. "
        "Keep responses concise and conversational. You can be interrupted at any time.\n\n"
        "Screenshot coordinate space: 1280×720 pixels.\n\n"
    )
    if memory_context:
        base += memory_context + "\n\n"
    base += (
        "If this is the start of a new session and you have memory context above, "
        "greet the user briefly and mention what they were last working on."
    )
    return base


# ── Mic input ────────────────────────────────────────────────────────────────

def _mic_reader_thread(stream: pyaudio.Stream, loop: asyncio.AbstractEventLoop) -> None:
    """Runs in a daemon thread. Reads mic chunks → puts into audio_in_queue."""
    while True:
        try:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            asyncio.run_coroutine_threadsafe(audio_in_queue.put(data), loop)
        except OSError as exc:
            print(f"[audio] mic read error: {exc}")
            break


async def send_audio_loop(session: genai.live.AsyncSession) -> None:
    """Drains audio_in_queue and streams to Live API."""
    sent_count = 0
    while True:
        data = await audio_in_queue.get()
        sent_count += 1
        if sent_count == 1:
            print("[mic] first audio chunk sent — mic is live")
        if sent_count % 200 == 0:
            print(f"[mic] {sent_count} chunks sent")
        try:
            await session.send_realtime_input(
                audio=types.Blob(data=data, mime_type="audio/pcm;rate=16000"),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[audio] send failed: {exc}")


# ── Speaker output ───────────────────────────────────────────────────────────

def _speaker_writer_thread(
    stream: pyaudio.Stream,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Runs in a daemon thread. Drains audio_out_queue → writes to speaker."""
    while True:
        future = asyncio.run_coroutine_threadsafe(audio_out_queue.get(), loop)
        chunk = future.result()
        if chunk is None:
            break  # sentinel: session ended
        try:
            stream.write(chunk)
        except OSError as exc:
            print(f"[audio] speaker write error: {exc}")


# ── Computer use execution ────────────────────────────────────────────────────

def _scale_coordinates(x: int, y: int) -> tuple[int, int]:
    """
    Scale click coordinates from 1280×720 screenshot space to actual screen resolution.
    Required for HiDPI/Retina displays where screen_width > 1280.
    """
    screen_w, screen_h = pyautogui.size()
    actual_x = int(x * screen_w / 1280)
    actual_y = int(y * screen_h / 720)
    return actual_x, actual_y


async def execute_computer_use(fn_name: str, fn_args: dict) -> str:
    """Execute a computer use action. Returns a status string for the tool response."""
    try:
        if fn_name == "click_at":
            x, y = int(fn_args["x"]), int(fn_args["y"])
            button = fn_args.get("button", "left")
            actual_x, actual_y = _scale_coordinates(x, y)
            if button == "double":
                await asyncio.to_thread(pyautogui.doubleClick, actual_x, actual_y)
            elif button == "right":
                await asyncio.to_thread(pyautogui.rightClick, actual_x, actual_y)
            else:
                await asyncio.to_thread(pyautogui.click, actual_x, actual_y)
            print(f"[cua] click ({button}) at screen ({actual_x}, {actual_y})")
            return f"Clicked at ({x}, {y})"

        elif fn_name == "type_text":
            text = fn_args["text"]
            # Use clipboard paste for unicode-safe typing on macOS
            proc = await asyncio.to_thread(
                subprocess.run, ["pbcopy"], input=text.encode(), capture_output=True
            )
            if proc.returncode != 0:
                return f"pbcopy failed: {proc.stderr.decode()}"
            await asyncio.sleep(0.1)  # let clipboard settle
            await asyncio.to_thread(pyautogui.hotkey, "command", "v")
            print(f"[cua] typed: {text[:60]}")
            return f"Typed: {text[:60]}{'...' if len(text) > 60 else ''}"

        elif fn_name == "open_app":
            app_name = fn_args["app_name"]
            proc = await asyncio.to_thread(
                subprocess.run, ["open", "-a", app_name], capture_output=True
            )
            if proc.returncode != 0:
                return f"Could not open {app_name}: {proc.stderr.decode()}"
            print(f"[cua] opened app: {app_name}")
            return f"Opened {app_name}"

        elif fn_name == "press_key":
            key = fn_args["key"]
            parts = [p.strip() for p in key.split("+")]
            if len(parts) == 1:
                await asyncio.to_thread(pyautogui.press, parts[0])
            else:
                await asyncio.to_thread(pyautogui.hotkey, *parts)
            print(f"[cua] pressed: {key}")
            return f"Pressed {key}"

        return f"Unknown tool: {fn_name}"

    except Exception as exc:  # noqa: BLE001
        print(f"[cua] {fn_name} failed: {exc}")
        return f"Error executing {fn_name}: {exc}"


# ── Receive loop ─────────────────────────────────────────────────────────────

async def receive_loop(
    session: genai.live.AsyncSession,
    session_id: str,
) -> None:
    """
    Receives responses from Live API:
      - Audio data → audio_out_queue
      - Tool calls → execute computer use actions
      - Text transcription → save to Firestore
    """
    _bg_tasks: set = set()  # keep references so GC doesn't drop fire-and-forget tasks
    msg_count = 0
    print("[recv] loop started")

    try:
        async for response in session.receive():
            msg_count += 1
            # ── Log every response type ───────────────────────────────────────
            parts = []
            if response.tool_call:
                parts.append("tool_call")
            if response.data:
                parts.append(f"audio({len(response.data)}b)")
            if response.server_content:
                sc = response.server_content
                if sc.turn_complete:
                    parts.append("turn_complete")
                if sc.interrupted:
                    parts.append("interrupted")
                if sc.output_transcription and sc.output_transcription.text:
                    parts.append(f"model_said: \"{sc.output_transcription.text[:60]}\"")
                if sc.input_transcription and sc.input_transcription.text:
                    parts.append(f"user_said: \"{sc.input_transcription.text[:60]}\"")
                if sc.model_turn and sc.model_turn.parts:
                    for p in sc.model_turn.parts:
                        if p.thought:
                            parts.append("thought")
                        if p.text:
                            parts.append(f"text: \"{p.text[:40]}\"")
            if parts:
                print(f"[recv] {' | '.join(parts)}")

            # ── Tool calls ────────────────────────────────────────────────────
            if response.tool_call:
                for fn_call in response.tool_call.function_calls:
                    fn_name = fn_call.name
                    fn_args = dict(fn_call.args) if fn_call.args else {}
                    print(f"[tool] {fn_name}({fn_args})")

                    if fn_name == "get_screen_context":
                        # Capture screenshot → describe locally with Gemini Flash.
                        try:
                            raw = await asyncio.to_thread(_screen._capture_raw)
                            _screen.cached_screenshot_raw = raw
                            # Use local Gemini call instead of Cloud Run /vision
                            vision_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
                            vision_resp = await vision_client.aio.models.generate_content(
                                model="gemini-2.5-flash",
                                contents=types.Content(
                                    role="user",
                                    parts=[
                                        types.Part(text="Describe what's on this screen in 2-3 sentences."),
                                        types.Part(inline_data=types.Blob(data=raw, mime_type="image/jpeg")),
                                    ],
                                ),
                            )
                            description = vision_resp.text or "Could not describe screen."
                            print(f"[screen] description: {description[:80]}")
                            result = description
                        except Exception as exc:  # noqa: BLE001
                            print(f"[screen] capture/vision failed: {exc}")
                            result = "Screen capture failed."
                    else:
                        result = await execute_computer_use(fn_name, fn_args)
                        # No post-action screenshot — sending video mid-session breaks audio

                    await session.send_tool_response(
                        function_responses=types.FunctionResponse(
                            id=fn_call.id,
                            name=fn_call.name,
                            response={"result": result},
                        )
                    )

            # ── Audio output ─────────────────────────────────────────────────
            if response.data:
                await audio_out_queue.put(response.data)

            # ── Model transcription: save model turn to Firestore ─────────────
            if response.server_content and response.server_content.output_transcription:
                text = response.server_content.output_transcription.text
                if text:
                    t = asyncio.create_task(
                        save_turn(session_id=session_id, role="model", text=text)
                    )
                    _bg_tasks.add(t)
                    t.add_done_callback(_bg_tasks.discard)

            # ── User transcription: save user turn to Firestore ───────────────
            if response.server_content and response.server_content.input_transcription:
                text = response.server_content.input_transcription.text
                if text:
                    t = asyncio.create_task(
                        save_turn(session_id=session_id, role="user", text=text)
                    )
                    _bg_tasks.add(t)
                    t.add_done_callback(_bg_tasks.discard)

    except Exception as exc:  # noqa: BLE001
        print(f"[recv] EXCEPTION after {msg_count} messages: {type(exc).__name__}: {exc}")
        raise
    finally:
        print(f"[recv] loop exited after {msg_count} messages")


# ── Main ─────────────────────────────────────────────────────────────────────

async def run() -> None:
    # Validate required env vars early
    if not os.environ.get("GEMINI_API_KEY"):
        print("[ghostops] missing GEMINI_API_KEY — add it to .env")
        sys.exit(1)

    session_id = os.environ.get("FIRESTORE_SESSION_ID", str(uuid.uuid4()))
    print(f"[ghostops] session_id={session_id}")

    # 1. Load memory from Firestore (skip gracefully if backend unavailable)
    memory_context = ""
    if os.environ.get("CLOUD_RUN_URL"):
        print("[ghostops] loading memory...")
        memory_turns = await load_memory(session_id=session_id, limit=10)
        memory_context = turns_to_context(memory_turns)
        print(f"[ghostops] loaded {len(memory_turns)} memory turns")
    else:
        print("[ghostops] no CLOUD_RUN_URL — starting without memory")

    # 2. Build system prompt
    system_prompt = build_system_prompt(memory_context)

    # 3. Gemini Live API config with computer use tools
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part(text=system_prompt)]
        ),
        tools=[types.Tool(function_declarations=[GET_SCREEN_CONTEXT, CLICK_AT, TYPE_TEXT, OPEN_APP, PRESS_KEY])],
        output_audio_transcription=types.AudioTranscriptionConfig(),
        input_audio_transcription=types.AudioTranscriptionConfig(),
    )

    # 4. Init PyAudio
    pya = pyaudio.PyAudio()
    try:
        mic_stream = pya.open(
            format=FORMAT, channels=CHANNELS, rate=SEND_SAMPLE_RATE,
            input=True, frames_per_buffer=CHUNK_SIZE,
        )
        speaker_stream = pya.open(
            format=FORMAT, channels=CHANNELS, rate=RECV_SAMPLE_RATE,
            output=True, frames_per_buffer=CHUNK_SIZE,
        )
    except OSError as exc:
        print(f"[ghostops] audio device error: {exc}")
        print("  → Check microphone permissions in System Settings > Privacy > Microphone")
        pya.terminate()
        sys.exit(1)

    # 5. Connect to Live API
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    loop = asyncio.get_event_loop()

    print("[ghostops] connecting to Gemini Live API...")
    async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
        print("[ghostops] connected — GhostOps is live (voice + vision + computer use)")

        # 6. Start mic reader thread
        mic_thread = threading.Thread(
            target=_mic_reader_thread,
            args=(mic_stream, loop),
            daemon=True,
        )
        mic_thread.start()

        # Start speaker writer thread
        speaker_thread = threading.Thread(
            target=_speaker_writer_thread,
            args=(speaker_stream, loop),
            daemon=True,
        )
        speaker_thread.start()

        # 7. Send a greeting so user hears audio immediately (confirms it's working)
        await session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[types.Part(text="Session started. Greet me briefly.")],
            )
        )
        print("[ghostops] greeting sent — you should hear audio now")

        # 8. Run audio send + receive concurrently
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(send_audio_loop(session))
                tg.create_task(receive_loop(session, session_id))
        except* KeyboardInterrupt:
            print("\n[ghostops] shutting down...")
        finally:
            # Signal speaker thread to stop
            await audio_out_queue.put(None)
            mic_stream.stop_stream()
            mic_stream.close()
            speaker_stream.stop_stream()
            speaker_stream.close()
            pya.terminate()
            print("[ghostops] session ended")


def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
