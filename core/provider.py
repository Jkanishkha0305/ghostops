"""
Provider switcher — auto-selects AI backend based on environment variable.

Set AI_PROVIDER in .env to control which backend is used:
    AI_PROVIDER=do       → DigitalOcean Gradient AI (default)
    AI_PROVIDER=gemini   → Google Gemini
    AI_PROVIDER=groq     → Groq

All providers expose the same async API:
    generate_text, generate_vision, generate_vision_with_tools, transcribe_audio
"""
import os

_PROVIDER = os.environ.get("AI_PROVIDER", "do").lower().strip()

if _PROVIDER == "gemini":
    from core.gemini_provider import (  # noqa: F401
        generate_text,
        generate_vision,
        generate_vision_with_tools,
        transcribe_audio,
    )
elif _PROVIDER == "groq":
    from core.groq_provider import (  # noqa: F401
        generate_text,
        generate_vision,
        generate_vision_with_tools,
        transcribe_audio,
    )
else:
    # Default: DigitalOcean Gradient AI
    from core.do_provider import (  # noqa: F401
        generate_text,
        generate_vision,
        generate_vision_with_tools,
        transcribe_audio,
    )
