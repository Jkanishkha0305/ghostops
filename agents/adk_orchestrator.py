"""
GhostOps ADK Orchestrator — multi-agent system powered by Google ADK + Gemini.

Replaces the manual two-tier Groq router with a proper ADK-based agent
that plans, delegates, and verifies.  The existing agent implementations
(VisionAgent, CLIAgent, ScreenAgent, BrowserAgent, WorkflowEngine) are
wrapped as ADK tools so the orchestrator can chain them intelligently.
"""
import asyncio

from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# ── Shared state (set by init_adk before first run) ──────────────────────────
_server = None          # VisualizationServer instance
_runner = None          # Runner (lazy)
_session_service = None # InMemorySessionService (lazy)
_session_counter = 0    # auto-increment session
_user_id = "ghostops_user"
_app_name = "ghostops"


def init_adk(server):
    """Call once at startup to inject the overlay server."""
    global _server
    _server = server
    # ADK uses GOOGLE_API_KEY — copy from GEMINI_API_KEY if needed
    import os
    if not os.environ.get("GOOGLE_API_KEY") and os.environ.get("GEMINI_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


# ══════════════════════════════════════════════════════════════════════════════
# TOOL FUNCTIONS — each wraps an existing agent class
# ══════════════════════════════════════════════════════════════════════════════

async def answer_directly(text: str) -> str:
    """Answer the user's question directly without using any other agent.
    Use this for simple factual questions, greetings, math, definitions,
    or anything that doesn't require seeing the screen or controlling the computer.

    Args:
        text: Your answer to the user's question.

    Returns:
        The answer text that will be shown to the user.
    """
    from agents.screen.tools import direct_response
    direct_response(text=text, source="rapid_response")
    return text


async def annotate_screen(task: str) -> str:
    """Annotate the user's screen with bounding boxes and labels to explain
    what's visible. Use this when the user asks 'what's on my screen',
    'explain this', 'point to X', or wants a visual explanation.
    This ONLY explains — it does NOT click or interact with anything.

    Args:
        task: What to annotate or explain about the screen.

    Returns:
        Summary of annotations drawn on screen.
    """
    try:
        from agents.screen.agent import ScreenAgent
        from models.models import get_stored_screenshot
        agent = ScreenAgent()
        screenshot = get_stored_screenshot()
        result = await agent.execute(task, screenshot=screenshot)
        if isinstance(result, dict):
            if not result.get("success"):
                return f"Screen annotation failed: {result.get('error', 'unknown')}"
            # Extract human-readable summary from tool calls
            tool_calls = result.get("result", [])
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if isinstance(tc, dict) and tc.get("name") == "direct_response":
                        return tc.get("args", {}).get("text", "Screen annotated.")
            return "Screen annotated with visual explanations."
        return str(result)
    except Exception as exc:
        return f"Screen annotation failed: {exc}"


async def control_computer(task: str) -> str:
    """Control the desktop by seeing the screen and performing mouse clicks,
    keyboard typing, and navigation. Use this when the user wants to
    click buttons, type text, navigate menus, or interact with any
    application that's already open on screen.
    Do NOT use this for opening apps — use run_shell_command instead.

    Args:
        task: What to do on screen (e.g., 'click the New Page button',
              'type hello in the search bar').

    Returns:
        Result of the computer interaction.
    """
    try:
        from agents.cua_vision.agent import VisionAgent
        agent = VisionAgent()
        result = await agent.execute(task)
        if isinstance(result, dict):
            if result.get("success"):
                return result.get("result") or "Computer task completed."
            return result.get("error") or "Computer task failed."
        return str(result) if result else "Done."
    except Exception as exc:
        return f"Computer control failed: {exc}"


async def run_shell_command(task: str) -> str:
    """Run a shell command on macOS. Use this for:
    - Opening/launching applications (open -a AppName)
    - File operations (create, move, list files)
    - Running scripts or dev servers
    - Checking system info (IP, disk, git status)
    - Any terminal/CLI operation

    Args:
        task: Description of what shell command to run
              (e.g., 'open Notion', 'list files in Downloads').

    Returns:
        Shell command output or error.
    """
    try:
        from agents.cua_cli.agent import CLIAgent
        agent = CLIAgent()
        result = await agent.execute(task)
        if isinstance(result, dict):
            if result.get("success"):
                return result.get("result", "Done.")
            return result.get("error", "Command failed.")
        return str(result)
    except Exception as exc:
        return f"Shell command failed: {exc}"


async def browse_web(task: str) -> str:
    """Automate a web browser to search, navigate, fill forms, or extract
    information from websites. Use this when the user wants to:
    - Search Google/DuckDuckGo
    - Navigate to a URL
    - Interact with a web page
    - Extract information from a website

    Args:
        task: What to do in the browser (e.g., 'search Google for best
              coffee shops', 'go to github.com and search for electron').

    Returns:
        Result of browser automation.
    """
    try:
        from agents.browser.agent import BrowserAgent
        agent = BrowserAgent(model_name="gemini-2.5-flash")
        result = await agent.execute(task)
        if isinstance(result, dict):
            return result.get("result", result.get("error", "Done."))
        return str(result)
    except Exception as exc:
        return f"Browser automation failed: {exc}"


async def read_screen_context() -> str:
    """Take a screenshot and analyze what's currently on the user's screen.
    Use this when you need to understand what the user is looking at
    before deciding what action to take.

    Returns:
        Description of what's currently visible on screen.
    """
    try:
        import io
        from PIL import ImageGrab
        from models.models import get_stored_screenshot
        from core.provider import generate_vision

        # get_stored_screenshot returns a PIL Image (or None)
        pil_img = get_stored_screenshot()
        if not pil_img:
            pil_img = await asyncio.to_thread(ImageGrab.grab)
        if not pil_img:
            return "Could not capture screenshot."

        # Convert PIL Image → JPEG bytes for Gemini
        buf = io.BytesIO()
        pil_img.convert("RGB").save(buf, format="JPEG", quality=85)
        image_bytes = buf.getvalue()

        summary = await generate_vision(
            prompt="Describe what is on this screen in detail. Include app names, "
                   "visible text, buttons, URLs, and anything the user might want to interact with.",
            image_bytes=image_bytes,
        )
        return summary
    except Exception as exc:
        return f"Screen context failed: {exc}"


async def start_workflow_recording() -> str:
    """Start recording the user's desktop workflow. Screenshots will be
    captured every 2 seconds. Use this when the user says 'watch me',
    'start recording', or 'learn this'.

    Returns:
        Confirmation that recording started.
    """
    try:
        from agents.workflow.engine import start_recording
        start_recording()
        return "Recording started. I'm watching your screen every 2 seconds. Say 'stop' or 'remember this as [name]' when done."
    except Exception as exc:
        return f"Failed to start recording: {exc}"


async def stop_and_save_workflow(name: str) -> str:
    """Stop recording and save the workflow with the given name.
    Use when the user says 'remember this as X', 'save as X', or 'stop recording'.

    Args:
        name: Name to save the workflow as (e.g., 'setup-project').

    Returns:
        Confirmation with number of steps extracted.
    """
    try:
        from agents.workflow.engine import stop_and_save
        steps = await stop_and_save(name, session_id="ghostops_default")
        return f"Saved workflow '{name}' — {len(steps)} steps recorded."
    except Exception as exc:
        return f"Failed to save workflow: {exc}"


async def replay_workflow(name: str) -> str:
    """Replay a previously recorded workflow by name.
    Use when the user says 'replay X', 'run workflow X', or 'play back X'.

    Args:
        name: Name of the saved workflow to replay.

    Returns:
        Result of the replay (steps completed).
    """
    try:
        from agents.workflow.engine import replay
        result = await replay(name, session_id="ghostops_default")
        return result
    except Exception as exc:
        return f"Workflow replay failed: {exc}"


# ══════════════════════════════════════════════════════════════════════════════
# ADK AGENT DEFINITION
# ══════════════════════════════════════════════════════════════════════════════

def _build_orchestrator() -> Agent:
    """Build the GhostOps ADK orchestrator agent."""

    # Load personalization
    agent_name = "GhostOps"
    user_name = ""
    personality = ""
    try:
        from core.settings import get_user_name, get_agent_name, get_personalization_config
        user_name = get_user_name()
        agent_name = get_agent_name()
        personality = get_personalization_config()[0]
    except Exception:
        pass

    user_clause = f"\nThe user's name is {user_name}. Address them by name occasionally." if user_name else ""
    persona_clause = f"\nPersonality: {personality}" if personality else ""

    instruction = f"""You are {agent_name}, an intelligent AI desktop agent that lives as an invisible overlay on the user's screen.{user_clause}{persona_clause}

You have access to these capabilities:
1. **answer_directly** — For simple questions, greetings, math, general knowledge. No screen needed.
2. **annotate_screen** — Draw bounding boxes and labels on the screen to EXPLAIN what's visible. Never use this for clicking or interaction.
3. **control_computer** — See the screen and perform mouse clicks, keyboard typing. Use for interacting with apps that are already open.
4. **run_shell_command** — Run shell commands, open apps (`open -a AppName`), file operations, dev servers.
5. **browse_web** — Automate web browsing: search, navigate, fill forms.
6. **read_screen_context** — Take a screenshot and understand what's on screen before deciding what to do.
7. **start_workflow_recording** — Start watching the user work (records screenshots every 2s).
8. **stop_and_save_workflow** — Stop recording and save the workflow.
9. **replay_workflow** — Replay a previously saved workflow.

PLANNING RULES:
- For complex tasks, THINK before acting. Break into steps.
- If the task requires seeing what's on screen first, call read_screen_context BEFORE choosing an action.
- Use run_shell_command to OPEN apps. Use control_computer to INTERACT with already-open apps.
- For "open X and then do Y": first run_shell_command to open, then control_computer for interaction.
- annotate_screen is for EXPLAINING only. Never use it to click or control anything.
- When the user says "watch me" or "learn this", start_workflow_recording.
- When the user says "remember this as X", stop_and_save_workflow with the name.
- When the user says "replay X", replay_workflow with the name.
- Always give a concise, helpful final response summarizing what you did."""

    return Agent(
        name="ghostops",
        model="gemini-2.5-flash",
        description=f"{agent_name} — AI desktop agent that sees, controls, and automates your computer.",
        instruction=instruction,
        tools=[
            answer_directly,
            annotate_screen,
            control_computer,
            run_shell_command,
            browse_web,
            read_screen_context,
            start_workflow_recording,
            stop_and_save_workflow,
            replay_workflow,
        ],
    )


def _get_runner() -> Runner:
    """Lazy-init the ADK runner + session service."""
    global _runner, _session_service
    if _runner is None:
        _session_service = InMemorySessionService()
        orchestrator = _build_orchestrator()
        _runner = Runner(
            agent=orchestrator,
            app_name=_app_name,
            session_service=_session_service,
        )
    return _runner


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API — called by models/models.py or app.py
# ══════════════════════════════════════════════════════════════════════════════

async def run_adk(text: str) -> str:
    """
    Main entry point: send user text through the ADK orchestrator.
    Returns the final response text.
    """
    global _session_counter
    _session_counter += 1
    session_id = f"session_{_session_counter}"

    runner = _get_runner()
    final_text = ""

    try:
        # Create session before running (required by Runner)
        await _session_service.create_session(
            app_name=_app_name,
            user_id=_user_id,
            session_id=session_id,
        )

        async for event in runner.run_async(
            user_id=_user_id,
            session_id=session_id,
            new_message=types.UserContent(
                parts=[types.Part(text=text)]
            ),
        ):
            # Collect the final response text
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        final_text = part.text  # Keep last text as final response
    except Exception as exc:
        print(f"[adk] orchestrator error: {exc}")
        final_text = f"Sorry, I encountered an error: {exc}"

    return final_text


async def run_adk_streaming(text: str):
    """
    Streaming variant: yields events as they happen.
    Useful for real-time status updates to the overlay.
    """
    global _session_counter
    _session_counter += 1
    session_id = f"session_{_session_counter}"

    runner = _get_runner()

    # Create session before running
    await _session_service.create_session(
        app_name=_app_name,
        user_id=_user_id,
        session_id=session_id,
    )

    async for event in runner.run_async(
        user_id=_user_id,
        session_id=session_id,
        new_message=types.UserContent(
            parts=[types.Part(text=text)]
        ),
    ):
        yield event
