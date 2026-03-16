"""
Groq provider — temporary swap for testing (saves Gemini quota).

To re-enable Gemini: set USE_GROQ=false in .env (or remove it).
To keep Groq: set USE_GROQ=true in .env.

Usage:
    from core.groq_provider import generate_text, generate_vision, generate_vision_with_tools
    text = await generate_text(system="...", user="...")
    desc = await generate_vision(prompt="...", image_bytes=raw_jpeg)
    calls = await generate_vision_with_tools(system="...", user_text="...", image_bytes=..., tools=[...])
"""
import asyncio
import base64
import json
import os

from groq import AsyncGroq

GROQ_TEXT_MODEL   = "llama-3.1-8b-instant"      # 500K TPD (was llama-3.3-70b-versatile @ 100K TPD)
GROQ_VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"  # 500K TPD, only vision model available

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])
    return _client


async def generate_text(
    system: str,
    user: str,
    temperature: float = 0.1,
    max_tokens: int = 256,
) -> str:
    """Drop-in for Gemini text generation."""
    resp = await _get_client().chat.completions.create(
        model=GROQ_TEXT_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


async def generate_vision(
    prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    max_tokens: int = 1024,
) -> str:
    """Drop-in for Gemini vision (screenshot analysis)."""
    b64 = base64.b64encode(image_bytes).decode()
    resp = await _get_client().chat.completions.create(
        model=GROQ_VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:{mime_type};base64,{b64}"
                }},
            ],
        }],
        max_tokens=max_tokens,
    )
    return (resp.choices[0].message.content or "").strip()


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio using Groq Whisper. Returns transcript text."""
    resp = await _get_client().audio.transcriptions.create(
        model="whisper-large-v3-turbo",
        file=(filename, audio_bytes),
        response_format="text",
    )
    return str(resp).strip()


async def generate_vision_with_tools(
    system: str,
    user_text: str,
    image_bytes: bytes,
    tools: list[dict],
    mime_type: str = "image/jpeg",
    max_tokens: int = 4096,
) -> list[dict]:
    """Vision + function calling for screen annotation. Returns list of {name, args} dicts."""
    b64 = base64.b64encode(image_bytes).decode()
    messages = [{"role": "system", "content": system}]
    user_content: list[dict] = [{"type": "text", "text": user_text}]
    if image_bytes:
        user_content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}})
    messages.append({"role": "user", "content": user_content})

    resp = await _get_client().chat.completions.create(
        model=GROQ_VISION_MODEL,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        max_tokens=max_tokens,
    )
    msg = resp.choices[0].message
    if not msg.tool_calls:
        text = (msg.content or "Done.").strip()
        return [{"name": "direct_response", "args": {"text": text}}]
    return [
        {"name": tc.function.name, "args": json.loads(tc.function.arguments)}
        for tc in msg.tool_calls
    ]
