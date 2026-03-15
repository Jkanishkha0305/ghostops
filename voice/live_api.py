"""
GhostOps Voice Module — Gemini Live API
========================================
Streams mic → Gemini Live API → speaker.
Handles tool calls:
  - get_screen_context()    — screenshot → local Gemini describe
  - execute_task(desc)      — delegates to ADK router
  - start_recording()       — begins workflow recording
  - stop_recording(name)    — stops and saves workflow
  - replay_workflow(name)   — replays a saved workflow
  - click_at / type_text / open_app / press_key  — computer use
"""

import asyncio
import os
import subprocess
import threading
import uuid

import pyaudio
import pyautogui
from dotenv import load_dotenv
from google import genai
from google.genai import types

from desktop import screen as _screen
from desktop.memory_client import load_memory, save_turn
from backend.memory import turns_to_context
from agents.workflow import engine as _workflow_engine

load_dotenv()

# ── Audio constants ───────────────────────────────────────────────────────────
FORMAT           = pyaudio.paInt16
CHANNELS         = 1
SEND_SAMPLE_RATE = 16_000
RECV_SAMPLE_RATE = 24_000
CHUNK_SIZE       = 1_024

LIVE_MODEL = "gemini-2.5-flash-native-audio-latest"

# ── Tool declarations ─────────────────────────────────────────────────────────
_TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_screen_context",
        description=(
            "Captures a live screenshot and describes what's on screen. "
            "Call when the user references their screen or before computer-use actions."
        ),
        parameters=types.Schema(type=types.Type.OBJECT, properties={}),
    ),
    types.FunctionDeclaration(
        name="execute_task",
        description=(
            "Delegate a complex multi-step task to the GhostOps AI agent (ADK router). "
            "Use for tasks like 'open the repo and run tests', 'search the web for X', "
            "or any task that requires browser/CLI/vision agents."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "description": types.Schema(
                    type=types.Type.STRING, description="Full task description"
                )
            },
            required=["description"],
        ),
    ),
    types.FunctionDeclaration(
        name="start_recording",
        description="Start recording a workflow. The agent will watch what you do.",
        parameters=types.Schema(type=types.Type.OBJECT, properties={}),
    ),
    types.FunctionDeclaration(
        name="stop_recording",
        description="Stop recording and save the workflow under a name.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "name": types.Schema(
                    type=types.Type.STRING, description="Name for this workflow"
                )
            },
            required=["name"],
        ),
    ),
    types.FunctionDeclaration(
        name="replay_workflow",
        description="Replay a previously recorded workflow by name.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "name": types.Schema(
                    type=types.Type.STRING, description="Name of the workflow to replay"
                )
            },
            required=["name"],
        ),
    ),
    types.FunctionDeclaration(
        name="click_at",
        description=(
            "Click at pixel coordinates (1280×720 space). "
            "Always call get_screen_context first to see what's on screen."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "x": types.Schema(type=types.Type.INTEGER, description="X coordinate (0-1280)"),
                "y": types.Schema(type=types.Type.INTEGER, description="Y coordinate (0-720)"),
                "button": types.Schema(
                    type=types.Type.STRING,
                    description="'left' (default), 'right', or 'double'",
                ),
            },
            required=["x", "y"],
        ),
    ),
    types.FunctionDeclaration(
        name="type_text",
        description="Type text at the current cursor position.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "text": types.Schema(type=types.Type.STRING, description="Text to type")
            },
            required=["text"],
        ),
    ),
    types.FunctionDeclaration(
        name="open_app",
        description="Open a macOS application by name (e.g. 'Safari', 'Terminal', 'VS Code').",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "app_name": types.Schema(type=types.Type.STRING, description="App name")
            },
            required=["app_name"],
        ),
    ),
    types.FunctionDeclaration(
        name="press_key",
        description="Press a key or hotkey (e.g. 'enter', 'command+c', 'command+space').",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "key": types.Schema(type=types.Type.STRING, description="Key or combo")
            },
            required=["key"],
        ),
    ),
]

# ── Shared queues ─────────────────────────────────────────────────────────────
audio_in_queue:  asyncio.Queue[bytes] = asyncio.Queue()
audio_out_queue: asyncio.Queue[bytes | None] = asyncio.Queue()


def build_system_prompt(memory_context: str) -> str:
    base = (
        "You are GhostOps, an AI desktop agent with persistent memory, on-demand screen vision, "
        "workflow recording/replay, and the ability to delegate complex tasks to specialized AI agents. "
        "Use get_screen_context to see the user's screen whenever it would help. "
        "You can control the Mac using: click_at, type_text, open_app, press_key. "
        "Always call get_screen_context before using click_at. "
        "For destructive actions (delete, send, submit), confirm with the user first. "
        "When user says 'watch me' or 'start recording', call start_recording(). "
        "When user says 'remember this as X', call stop_recording(name='X'). "
        "When user says 'run X' or 'replay X', call replay_workflow(name='X'). "
        "For complex multi-step tasks, use execute_task(). "
        "Keep responses concise and conversational.\n\n"
        "Screenshot coordinate space: 1280×720 pixels.\n\n"
    )
    if memory_context:
        base += memory_context + "\n\n"
    base += (
        "If this is the start of a new session and you have memory context above, "
        "greet the user briefly and mention what they were last working on."
    )
    return base


# ── Mic input ─────────────────────────────────────────────────────────────────

def _mic_reader_thread(stream: pyaudio.Stream, loop: asyncio.AbstractEventLoop) -> None:
    while True:
        try:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            asyncio.run_coroutine_threadsafe(audio_in_queue.put(data), loop)
        except OSError as exc:
            print(f"[audio] mic read error: {exc}")
            break


async def send_audio_loop(session) -> None:
    sent = 0
    while True:
        data = await audio_in_queue.get()
        sent += 1
        if sent == 1:
            print("[mic] live")
        try:
            await session.send_realtime_input(
                audio=types.Blob(data=data, mime_type="audio/pcm;rate=16000"),
            )
        except Exception as exc:
            print(f"[audio] send failed: {exc}")


# ── Speaker output ────────────────────────────────────────────────────────────

def _speaker_writer_thread(stream: pyaudio.Stream, loop: asyncio.AbstractEventLoop) -> None:
    while True:
        future = asyncio.run_coroutine_threadsafe(audio_out_queue.get(), loop)
        chunk = future.result()
        if chunk is None:
            break
        try:
            stream.write(chunk)
        except OSError as exc:
            print(f"[audio] speaker write error: {exc}")


# ── Computer use ──────────────────────────────────────────────────────────────

def _scale(x: int, y: int) -> tuple[int, int]:
    sw, sh = pyautogui.size()
    return int(x * sw / 1280), int(y * sh / 720)


async def _execute_cua(fn_name: str, fn_args: dict) -> str:
    try:
        if fn_name == "click_at":
            x, y = int(fn_args["x"]), int(fn_args["y"])
            button = fn_args.get("button", "left")
            ax, ay = _scale(x, y)
            if button == "double":
                await asyncio.to_thread(pyautogui.doubleClick, ax, ay)
            elif button == "right":
                await asyncio.to_thread(pyautogui.rightClick, ax, ay)
            else:
                await asyncio.to_thread(pyautogui.click, ax, ay)
            return f"Clicked at ({x}, {y})"
        elif fn_name == "type_text":
            text = fn_args["text"]
            proc = await asyncio.to_thread(
                subprocess.run, ["pbcopy"], input=text.encode(), capture_output=True
            )
            if proc.returncode != 0:
                return f"pbcopy failed: {proc.stderr.decode()}"
            await asyncio.sleep(0.1)
            await asyncio.to_thread(pyautogui.hotkey, "command", "v")
            return f"Typed: {text[:60]}"
        elif fn_name == "open_app":
            app = fn_args["app_name"]
            proc = await asyncio.to_thread(
                subprocess.run, ["open", "-a", app], capture_output=True
            )
            if proc.returncode != 0:
                return f"Could not open {app}: {proc.stderr.decode()}"
            return f"Opened {app}"
        elif fn_name == "press_key":
            key = fn_args["key"]
            parts = [p.strip() for p in key.split("+")]
            if len(parts) == 1:
                await asyncio.to_thread(pyautogui.press, parts[0])
            else:
                await asyncio.to_thread(pyautogui.hotkey, *parts)
            return f"Pressed {key}"
        return f"Unknown tool: {fn_name}"
    except Exception as exc:
        return f"Error: {exc}"


# ── Tool dispatch ─────────────────────────────────────────────────────────────

async def _handle_tool_call(fn_name: str, fn_args: dict, session_id: str) -> str:
    if fn_name == "get_screen_context":
        try:
            raw = await asyncio.to_thread(_screen._capture_raw)
            _screen.cached_screenshot_raw = raw
            client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
            resp = await client.aio.models.generate_content(
                model="gemini-2.0-flash",
                contents=types.Content(
                    role="user",
                    parts=[
                        types.Part(text="Describe what's on this screen in 2-3 sentences."),
                        types.Part(inline_data=types.Blob(data=raw, mime_type="image/jpeg")),
                    ],
                ),
            )
            return resp.text or "Could not describe screen."
        except Exception as exc:
            return f"Screen capture failed: {exc}"

    elif fn_name == "execute_task":
        desc = fn_args.get("description", "")
        print(f"[task] delegating to ADK: {desc}")
        try:
            from models.adk_agents import run_router_agent
            result = await run_router_agent(desc)
            return result or "Task completed."
        except Exception as exc:
            return f"Task failed: {exc}"

    elif fn_name == "start_recording":
        _workflow_engine.start_recording()
        return "Recording started. Perform your workflow — I'm watching."

    elif fn_name == "stop_recording":
        name = fn_args.get("name", "unnamed")
        try:
            steps = await _workflow_engine.stop_and_save(name, session_id)
            return f"Workflow '{name}' saved with {len(steps)} steps."
        except Exception as exc:
            return f"Failed to save workflow: {exc}"

    elif fn_name == "replay_workflow":
        name = fn_args.get("name", "")
        try:
            result = await _workflow_engine.replay(name, session_id)
            return result
        except Exception as exc:
            return f"Replay failed: {exc}"

    else:
        return await _execute_cua(fn_name, fn_args)


# ── Receive loop ──────────────────────────────────────────────────────────────

async def receive_loop(session, session_id: str) -> None:
    _bg: set = set()
    count = 0
    print("[recv] loop started")
    try:
        async for response in session.receive():
            count += 1

            if response.tool_call:
                for fn in response.tool_call.function_calls:
                    name = fn.name
                    args = dict(fn.args) if fn.args else {}
                    print(f"[tool] {name}({args})")
                    result = await _handle_tool_call(name, args, session_id)
                    await session.send_tool_response(
                        function_responses=types.FunctionResponse(
                            id=fn.id,
                            name=fn.name,
                            response={"result": result},
                        )
                    )

            if response.data:
                await audio_out_queue.put(response.data)
                # Forward to workflow engine if recording
                _workflow_engine.on_audio_chunk(response.data)

            if response.server_content:
                sc = response.server_content
                if sc.output_transcription and sc.output_transcription.text:
                    text = sc.output_transcription.text
                    t = asyncio.create_task(save_turn(session_id=session_id, role="model", text=text))
                    _bg.add(t); t.add_done_callback(_bg.discard)
                if sc.input_transcription and sc.input_transcription.text:
                    text = sc.input_transcription.text
                    _workflow_engine.on_transcription(text)
                    t = asyncio.create_task(save_turn(session_id=session_id, role="user", text=text))
                    _bg.add(t); t.add_done_callback(_bg.discard)

    except Exception as exc:
        print(f"[recv] exception after {count} messages: {exc}")
        raise
    finally:
        print(f"[recv] loop exited after {count} messages")


# ── Main entry point ──────────────────────────────────────────────────────────

async def run() -> None:
    import sys
    if not os.environ.get("GEMINI_API_KEY"):
        print("[ghostops] missing GEMINI_API_KEY")
        sys.exit(1)

    session_id = os.environ.get("FIRESTORE_SESSION_ID", str(uuid.uuid4()))
    print(f"[ghostops] session_id={session_id}")

    memory_context = ""
    if os.environ.get("CLOUD_RUN_URL"):
        memory_turns = await load_memory(session_id=session_id, limit=10)
        memory_context = turns_to_context(memory_turns)
        print(f"[ghostops] loaded {len(memory_turns)} memory turns")

    system_prompt = build_system_prompt(memory_context)
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part(text=system_prompt)]),
        tools=[types.Tool(function_declarations=_TOOL_DECLARATIONS)],
        output_audio_transcription=types.AudioTranscriptionConfig(),
        input_audio_transcription=types.AudioTranscriptionConfig(),
    )

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
        pya.terminate()
        sys.exit(1)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    loop = asyncio.get_event_loop()

    print("[ghostops] connecting to Gemini Live API...")
    async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
        print("[ghostops] connected — GhostOps is live")

        threading.Thread(target=_mic_reader_thread, args=(mic_stream, loop), daemon=True).start()
        threading.Thread(target=_speaker_writer_thread, args=(speaker_stream, loop), daemon=True).start()

        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text="Session started. Greet me briefly.")])
        )

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(send_audio_loop(session))
                tg.create_task(receive_loop(session, session_id))
        except* KeyboardInterrupt:
            print("\n[ghostops] shutting down...")
        finally:
            await audio_out_queue.put(None)
            mic_stream.stop_stream(); mic_stream.close()
            speaker_stream.stop_stream(); speaker_stream.close()
            pya.terminate()
            print("[ghostops] session ended")


async def run_with_reconnect() -> None:
    """Wraps run() with auto-reconnect on keepalive timeout or connection drop."""
    import sys
    retry_delay = 3
    while True:
        try:
            await run()
            break  # clean exit (KeyboardInterrupt propagated as normal exit)
        except KeyboardInterrupt:
            break
        except Exception as exc:
            msg = str(exc).lower()
            if "keepalive" in msg or "ping timeout" in msg or "1011" in msg or "connection" in msg:
                print(f"\n[ghostops] connection dropped ({exc}) — reconnecting in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
            else:
                print(f"[ghostops] fatal error: {exc}")
                sys.exit(1)


def main() -> None:
    try:
        asyncio.run(run_with_reconnect())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
