"""
Minimal bidirectional audio test.
Just talks to Gemini — no tools, no memory, no screen.
Use this to confirm multi-turn voice works before adding anything else.

Run:
  uv run python -m desktop.audio_test
"""

import asyncio
import os
import threading

import pyaudio
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

FORMAT           = pyaudio.paInt16
CHANNELS         = 1
SEND_SAMPLE_RATE = 16_000
RECV_SAMPLE_RATE = 24_000
CHUNK            = 1_024

MODEL       = "gemini-2.5-flash-native-audio-preview-12-2025"
API_VERSION = "v1beta"

audio_in_q:  asyncio.Queue = asyncio.Queue()
audio_out_q: asyncio.Queue = asyncio.Queue()


def _mic_thread(stream: pyaudio.Stream, loop: asyncio.AbstractEventLoop) -> None:
    while True:
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            asyncio.run_coroutine_threadsafe(audio_in_q.put(data), loop)
        except OSError:
            break


def _speaker_thread(stream: pyaudio.Stream, loop: asyncio.AbstractEventLoop) -> None:
    while True:
        future = asyncio.run_coroutine_threadsafe(audio_out_q.get(), loop)
        chunk = future.result()
        if chunk is None:
            break
        try:
            stream.write(chunk)
        except OSError:
            break


async def send_loop(session: genai.live.AsyncSession) -> None:
    while True:
        data = await audio_in_q.get()
        await session.send_realtime_input(
            audio=types.Blob(data=data, mime_type="audio/pcm;rate=16000")
        )


async def recv_loop(session: genai.live.AsyncSession) -> None:
    async for resp in session.receive():
        # Audio → speaker
        if resp.data:
            await audio_out_q.put(resp.data)
        # Log turn boundaries so we can see if multi-turn works
        if resp.server_content:
            if resp.server_content.turn_complete:
                print("  [turn complete — listening...]")
            if resp.server_content.interrupted:
                print("  [interrupted]")


async def run() -> None:
    if not os.environ.get("GEMINI_API_KEY"):
        print("Missing GEMINI_API_KEY in .env")
        return

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
    )

    pya = pyaudio.PyAudio()
    mic = pya.open(
        format=FORMAT, channels=CHANNELS, rate=SEND_SAMPLE_RATE,
        input=True, frames_per_buffer=CHUNK,
    )
    spk = pya.open(
        format=FORMAT, channels=CHANNELS, rate=RECV_SAMPLE_RATE,
        output=True, frames_per_buffer=CHUNK,
    )

    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options={"api_version": API_VERSION},
    )
    loop = asyncio.get_event_loop()

    print(f"Connecting to {MODEL} (api={API_VERSION})...")
    async with client.aio.live.connect(model=MODEL, config=config) as session:
        print("Connected! Start talking. Ctrl+C to quit.\n")

        threading.Thread(target=_mic_thread,     args=(mic, loop), daemon=True).start()
        threading.Thread(target=_speaker_thread, args=(spk, loop), daemon=True).start()

        try:
            await asyncio.gather(send_loop(session), recv_loop(session))
        except asyncio.CancelledError:
            pass
        finally:
            await audio_out_q.put(None)
            mic.stop_stream(); mic.close()
            spk.stop_stream(); spk.close()
            pya.terminate()
            print("\nSession ended.")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
