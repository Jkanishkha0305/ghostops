import os
import asyncio
import time
import io
import wave
import threading
import pyaudio
from google import genai
from google.genai import types
from dotenv import load_dotenv

from PIL import ImageGrab
from core.settings import set_host_and_port, set_screen_size, get_model_configs, get_screen_size

load_dotenv()

from models.models import call_gemini, store_screenshot
from agents.screen.tools import stop_all_actions
from agents.cua_vision.tools import (
    reset_state as reset_cua_vision_state,
    request_stop as request_cua_vision_stop,
)
from ui.server import VisualizationServer

FORMAT = pyaudio.paInt16
CHANNELS = 1
SAMPLE_RATE = 16_000
CHUNK = 1_024

_stop_recording = threading.Event()
_is_recording = False
_mic_task = None
_mic_thread = None

def _record_to_event() -> bytes:
    pya = pyaudio.PyAudio()
    stream = pya.open(
        format=FORMAT, channels=CHANNELS, rate=SAMPLE_RATE,
        input=True, frames_per_buffer=CHUNK,
    )
    frames = []
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
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    return buf.getvalue()

def _sync_transcribe(wav_bytes: bytes, rapid_model: str) -> str:
    client = genai.Client()
    response = client.models.generate_content(
        model=rapid_model,
        contents=[
            types.Part(inline_data=types.Blob(data=wav_bytes, mime_type="audio/wav")),
            "Please transcribe this audio exactly. Do not add any conversational filler, formatting, or thoughts. Return ONLY the transcribed text.",
        ]
    )
    return (response.text or "").strip()

async def transcribe_audio(wav_bytes: bytes, rapid_model: str, server: VisualizationServer):
    print("[mic] Transcribing audio with Gemini...")
    try:
        text = await asyncio.to_thread(_sync_transcribe, wav_bytes, rapid_model)
        print(f"[mic] Transcription: {text}")
        await server.send_mic_transcript(text, is_final=True)
    except Exception as exc:
        print(f"[mic] Transcription failed: {exc}")
        await server.send_mic_transcript("", is_final=True)

async def main():
    # Figure out open port and set it in settings.json
    settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
    host, port = set_host_and_port(settings_path)

    # Figure out dimensions of the user's screen and set it in settings.json.
    # Fallback to configured size if capture is unavailable at startup.
    try:
        screen_width, screen_height = await asyncio.wait_for(
            asyncio.to_thread(lambda: ImageGrab.grab().size),
            timeout=2.0,
        )
    except Exception as exc:
        try:
            screen_width, screen_height = get_screen_size(settings_path)
        except Exception:
            screen_width, screen_height = (1920, 1080)
        print(
            f"Screen capture unavailable at startup ({type(exc).__name__}: {exc}). "
            f"Using configured size {screen_width}x{screen_height}."
        )
    set_screen_size(screen_width, screen_height)

    # Retrieve model configs from settings
    rapid_response_model, screen_model = get_model_configs(settings_path)
    print(f"Models loaded - Rapid: {rapid_response_model}, GhostOps: {screen_model}")

    current_task = None
    task_lock = asyncio.Lock()
    last_overlay_text = ""
    last_overlay_ts = 0.0

    async def stop_all():
        nonlocal current_task
        print("Stop requested: cancelling active tasks.")
        request_cua_vision_stop()
        async with task_lock:
            task = current_task
        if task and not task.done():
            task.cancel()
        stop_all_actions()
        reset_cua_vision_state()

    async def _run_overlay_task(text: str):
        nonlocal current_task
        try:
            await call_gemini(text, rapid_response_model, screen_model)
        except asyncio.CancelledError:
            print("Active task cancelled.")
        except Exception as exc:
            print(f"Active task failed: {exc}")
            # Notify the UI so it can narrate "error"
            from agents.screen.tools import direct_response
            direct_response(f"Error: {exc}", source="error")
        finally:
            async with task_lock:
                if current_task is asyncio.current_task():
                    current_task = None

    async def handle_overlay_input(text):
        nonlocal current_task, last_overlay_text, last_overlay_ts
        text = text.strip()
        if not text:
            return
        now = time.monotonic()
        if text == last_overlay_text and (now - last_overlay_ts) < 1.2:
            print(f"Overlay input ignored (duplicate within 1.2s): {text}")
            return

        last_overlay_text = text
        last_overlay_ts = now
        async with task_lock:
            if current_task and not current_task.done():
                print("Overlay input ignored (task already running).")
                return
            print(f"Overlay input: {text}")
            task = asyncio.create_task(_run_overlay_task(text))
            current_task = task

    def start_mic():
        global _is_recording
        if not _is_recording:
            _is_recording = True
            print("[mic] Starting recording...")
            _stop_recording.clear()
            loop = asyncio.get_running_loop()
            
            def _recording_worker():
                import time
                time.sleep(0.1) # Let PyAudio device initialize
                pcm_bytes = _record_to_event()
                wav_bytes = _pcm_to_wav(pcm_bytes)
                asyncio.run_coroutine_threadsafe(
                    transcribe_audio(wav_bytes, rapid_response_model, server),
                    loop
                )
                        
            threading.Thread(target=_recording_worker, daemon=True).start()

    def stop_mic():
        global _is_recording
        if _is_recording:
            _is_recording = False
            print("[mic] Stopping recording...")
            _stop_recording.set()

    server = VisualizationServer(
        host=host,
        port=port,
        on_overlay_input=handle_overlay_input,
        on_capture_screenshot=store_screenshot,
        on_stop_all=stop_all,
        on_start_mic=start_mic,
        on_stop_mic=stop_mic
    )
    await server.start()
    print(f"Visualization server listening at ws://{host}:{port}")
    print("Waiting for overlay client connection...")
    await server.wait_for_client()
    print("Overlay client connected.")

    await server.wait_forever()


async def main_with_voice():
    """
    Full GhostOps entry point:
    1. Start the Electron overlay (GhostOps routing + screen annotation)
    2. Start the voice module (Gemini Live API)
    Both run concurrently.
    """
    # Start voice module in background thread (has its own asyncio.run)
    import threading

    def _voice_thread():
        from voice.live_api import run as voice_run
        asyncio.run(voice_run())

    voice_t = threading.Thread(target=_voice_thread, daemon=True)
    voice_t.start()
    print("[ghostops] voice module started in background thread")

    # Start overlay (blocks until overlay closes)
    await main()


if __name__ == '__main__':
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "overlay"
    try:
        if mode == "voice":
            from voice.live_api import main as voice_main
            voice_main()
        elif mode == "full":
            asyncio.run(main_with_voice())
        else:
            asyncio.run(main())
    finally:
        pass
