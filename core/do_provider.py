"""
DigitalOcean Gradient AI provider — serverless inference via OpenAI-compatible API.

Drop-in replacement for groq_provider / gemini_provider with identical async API surface:
    generate_text, generate_vision, generate_vision_with_tools, transcribe_audio

Base URL: https://inference.do-ai.run/v1/
Auth: Bearer $GRADIENT_MODEL_ACCESS_KEY
"""
import base64
import json
import os

from openai import AsyncOpenAI

DO_TEXT_MODEL = "llama3.3-70b-instruct"
DO_VISION_MODEL = "openai-gpt-4o"            # vision-capable on DO
DO_FAST_MODEL = "anthropic-claude-haiku-4.5"  # fast routing/classification

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("GRADIENT_MODEL_ACCESS_KEY", "")
        if not api_key:
            raise RuntimeError("GRADIENT_MODEL_ACCESS_KEY not set")
        _client = AsyncOpenAI(
            base_url="https://inference.do-ai.run/v1/",
            api_key=api_key,
        )
    return _client


async def generate_text(
    system: str,
    user: str,
    temperature: float = 0.1,
    max_tokens: int = 256,
) -> str:
    """Drop-in for text generation (routing, CLI commands, etc.)."""
    resp = await _get_client().chat.completions.create(
        model=DO_TEXT_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max(256, max_tokens),
    )
    return (resp.choices[0].message.content or "").strip()


async def generate_vision(
    prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    max_tokens: int = 1024,
) -> str:
    """Drop-in for vision (screenshot analysis)."""
    b64 = base64.b64encode(image_bytes).decode()
    resp = await _get_client().chat.completions.create(
        model=DO_VISION_MODEL,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:{mime_type};base64,{b64}"
                }},
            ],
        }],
        max_tokens=max(256, max_tokens),
    )
    return (resp.choices[0].message.content or "").strip()


async def generate_vision_with_tools(
    system: str,
    user_text: str,
    image_bytes: bytes,
    tools: list[dict],
    mime_type: str = "image/jpeg",
    max_tokens: int = 4096,
) -> list[dict]:
    """Vision + function calling. Returns list of {name, args} dicts."""
    b64 = base64.b64encode(image_bytes).decode()
    messages = [{"role": "system", "content": system}]
    user_content: list[dict] = [{"type": "text", "text": user_text}]
    if image_bytes:
        user_content.append({"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}})
    messages.append({"role": "user", "content": user_content})

    # Convert tool declarations to OpenAI format
    oai_tools = _convert_tools(tools)

    resp = await _get_client().chat.completions.create(
        model=DO_VISION_MODEL,
        messages=messages,
        tools=oai_tools if oai_tools else None,
        tool_choice="auto" if oai_tools else None,
        max_tokens=max(256, max_tokens),
    )
    msg = resp.choices[0].message
    if not msg.tool_calls:
        text = (msg.content or "Done.").strip()
        return [{"name": "direct_response", "args": {"text": text}}]
    return [
        {"name": tc.function.name, "args": json.loads(tc.function.arguments)}
        for tc in msg.tool_calls
    ]


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio — falls back to Groq Whisper since DO doesn't have STT."""
    try:
        from core.groq_provider import transcribe_audio as groq_transcribe
        return await groq_transcribe(audio_bytes, filename)
    except Exception:
        # Fallback to Gemini transcription
        from core.gemini_provider import transcribe_audio as gemini_transcribe
        return await gemini_transcribe(audio_bytes, filename)


def _convert_tools(tools: list) -> list[dict]:
    """Convert tool declarations to OpenAI function-calling format."""
    if not tools:
        return []
    oai_tools = []
    for tool in tools:
        if isinstance(tool, dict) and "name" in tool:
            oai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                },
            })
        elif isinstance(tool, dict) and "function" in tool:
            # Already in OpenAI format
            oai_tools.append(tool)
    return oai_tools
