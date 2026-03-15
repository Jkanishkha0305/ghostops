"""
GhostOps ADK Agent Wrappers
============================
Thin wrappers around existing agents for use from the voice module.
Each wrapper takes a task string and returns a result string.
"""

import asyncio
from typing import Optional

from agents.screen.agent import ScreenAgent
from agents.cua_vision.agent import VisionAgent
from agents.cua_cli.agent import CLIAgent


async def run_router_agent(task: str) -> str:
    """
    Routes a task to the best available agent based on heuristics.
    For hackathon: use CLI for shell tasks, Vision for GUI tasks, Screen for annotations.
    """
    task_lower = task.lower()
    
    # Heuristic routing
    if any(kw in task_lower for kw in ["annotate", "highlight", "explain screen", "what is", "describe"]):
        return await run_screen_agent(task)
    elif any(kw in task_lower for kw in ["click", "type", "open", "drag", "scroll", "gui", "window"]):
        return await run_desktop_agent(task)
    else:
        return await run_cli_agent(task)


async def run_screen_agent(query: str) -> str:
    """Wraps agents/screen/ annotation logic."""
    from models.models import get_stored_screenshot
    from agents.screen.prompts import SCREEN_SYSTEM_PROMPT
    from models.models import GeminiModel
    from core.settings import get_model_configs
    import os

    settings_path = os.path.join(os.path.dirname(__file__), "..", "settings.json")
    _, screen_model = get_model_configs(settings_path)
    model = GeminiModel(screen_model=screen_model)
    screenshot = get_stored_screenshot()
    prompt = SCREEN_SYSTEM_PROMPT + f"\n# User's Request:\n{query}"
    try:
        result = await model.generate_screen_response(prompt, screenshot)
        return result.get("summary") or "Screen annotation completed."
    except Exception as exc:
        return f"Screen agent failed: {exc}"


async def run_desktop_agent(task: str) -> str:
    """Wraps agents/cua_vision/ vision-action loop."""
    from core.settings import get_model_configs
    from models.models import get_stored_screenshot
    import os

    settings_path = os.path.join(os.path.dirname(__file__), "..", "settings.json")
    _, screen_model = get_model_configs(settings_path)
    screenshot = get_stored_screenshot()
    agent = VisionAgent(model_name=screen_model)
    try:
        result = await agent.execute(task, screenshot)
        if result.get("success"):
            return result.get("result") or "Desktop task completed."
        return result.get("error") or "Desktop task failed."
    except Exception as exc:
        return f"Desktop agent failed: {exc}"


async def run_cli_agent(task: str) -> str:
    """Wraps agents/cua_cli/ shell execution."""
    agent = CLIAgent()
    try:
        result = await agent.execute(task)
        if result.get("success"):
            return result.get("result") or "CLI task completed."
        return result.get("error") or "CLI task failed."
    except Exception as exc:
        return f"CLI agent failed: {exc}"


async def run_workflow_agent(task: str) -> str:
    """Placeholder for workflow agent (record/replay handled directly in workflow engine)."""
    return f"Workflow task: {task}"
