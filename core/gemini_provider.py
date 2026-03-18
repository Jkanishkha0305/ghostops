"""
Gemini provider — native Google GenAI SDK (replaces Groq for all LLM calls).

Drop-in replacement for groq_provider.py with identical async API surface:
    generate_text, generate_vision, generate_vision_with_tools, transcribe_audio
"""
import asyncio
import base64
import json
import os

from google import genai
from google.genai import types

GEMINI_MODEL = "gemini-2.5-flash"

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        _client = genai.Client(api_key=api_key)
    return _client


# ── Text generation ──────────────────────────────────────────────────────────

async def generate_text(
    system: str,
    user: str,
    temperature: float = 0.5,
    max_tokens: int = 1024,
) -> str:
    """Generate text (routing decisions, command generation, etc.)."""
    client = _get_client()
    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    return (response.text or "").strip()


# ── Vision (screenshot analysis) ─────────────────────────────────────────────

async def generate_vision(
    prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    max_tokens: int = 1024,
) -> str:
    """Send a screenshot + prompt, get text description back."""
    client = _get_client()
    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            types.Part.from_text(text=prompt),
        ],
        config=types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=max_tokens,
        ),
    )
    return (response.text or "").strip()


# ── Vision with tool calling ─────────────────────────────────────────────────

async def generate_vision_with_tools(
    system: str,
    user_text: str,
    image_bytes: bytes,
    tools: list,
    max_tokens: int = 2048,
    mime_type: str = "image/jpeg",
) -> list[dict]:
    """
    Send screenshot + prompt + tool schema, get back tool calls.

    Returns list of {name, args} dicts (same format as groq_provider).
    Falls back to [{"name": "direct_response", "args": {"text": ...}}] if
    the model returns plain text instead of tool calls.
    """
    client = _get_client()

    # Build Gemini-native tool declarations
    gemini_tools = _convert_tools_for_gemini(tools)

    contents = [
        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        types.Part.from_text(text=user_text),
    ]

    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.3,
        max_output_tokens=max_tokens,
        tools=gemini_tools if gemini_tools else None,
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="ANY")
        ) if gemini_tools else None,
    )

    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=config,
    )

    # Extract tool calls from response
    tool_calls = []
    if response.candidates:
        for part in response.candidates[0].content.parts:
            if part.function_call:
                fc = part.function_call
                tool_calls.append({
                    "name": fc.name,
                    "args": dict(fc.args) if fc.args else {},
                })

    # If no tool calls but we got text, wrap as direct_response
    if not tool_calls and response.text:
        tool_calls.append({
            "name": "direct_response",
            "args": {"text": response.text.strip()},
        })

    return tool_calls


# ── Audio transcription ──────────────────────────────────────────────────────

async def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.webm",
) -> str:
    """
    Transcribe audio using Gemini's audio understanding.
    Gemini can process audio natively — no separate Whisper endpoint needed.
    """
    client = _get_client()

    mime_map = {
        ".webm": "audio/webm",
        ".mp3": "audio/mp3",
        ".wav": "audio/wav",
        ".ogg": "audio/ogg",
        ".m4a": "audio/mp4",
    }
    ext = os.path.splitext(filename)[1].lower()
    mime_type = mime_map.get(ext, "audio/webm")

    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
            types.Part.from_text(text="Transcribe this audio exactly. Return ONLY the transcription, no commentary."),
        ],
        config=types.GenerateContentConfig(
            temperature=0.0,
            max_output_tokens=512,
        ),
    )
    return (response.text or "").strip()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _convert_tools_for_gemini(tools: list) -> list:
    """
    Convert tool declarations to Gemini-native format.
    Accepts either raw dicts (from existing tool declarations) or
    already-formatted Gemini tool objects.
    """
    if not tools:
        return []

    gemini_tools = []
    for tool in tools:
        if isinstance(tool, dict):
            # Raw dict format from existing code: {name, description, parameters}
            fn_decl = types.FunctionDeclaration(
                name=tool.get("name", ""),
                description=tool.get("description", ""),
                parameters=tool.get("parameters", {}),
            )
            gemini_tools.append(types.Tool(function_declarations=[fn_decl]))
        elif hasattr(tool, "function_declarations"):
            # Already a Gemini Tool object
            gemini_tools.append(tool)
        else:
            # Assume it's a Gemini-compatible object
            gemini_tools.append(tool)

    return gemini_tools
