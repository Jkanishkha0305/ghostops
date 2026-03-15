"""
CLI Agent — Direct shell execution via Gemini-generated commands.

Gemini 2.5 Flash receives the task, generates the shell command,
Python runs it directly via subprocess. No gemini-cli dependency.
"""
import asyncio
import os
import subprocess
from typing import Optional

from dotenv import load_dotenv
# [GEMINI] from google import genai
# [GEMINI] from google.genai import types
# [GROQ] using core.groq_provider instead
from core.groq_provider import generate_text

load_dotenv()

# Commands that are never allowed to run
_BLOCKED = {"rm -rf /", "mkfs", ":(){:|:&};:", "dd if=/dev/zero"}

_SYSTEM_PROMPT = """\
You are a macOS shell command generator. Given a task, output ONLY the shell command to run — no explanation, no markdown, no backticks, just the raw command.

Rules:
- Use macOS-compatible commands
- For opening apps: use `open -a AppName`
- For opening URLs: use `open URL`
- For file operations: use standard Unix commands
- For running scripts: use python3 / node / bash as appropriate
- If the task needs multiple commands, join with &&
- If you cannot generate a safe command, output: CANNOT_EXECUTE
"""


class CLIAgent:
    def __init__(self, model_name: str = "gemini-2.5-flash"):
        # [GEMINI] self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.model_name = model_name  # kept for interface compat, Groq model set in groq_provider

    async def _generate_command(self, task: str) -> Optional[str]:
        """Ask Groq to produce a shell command for the task."""
        # [GEMINI] resp = await self.client.aio.models.generate_content(
        # [GEMINI]     model=self.model_name,
        # [GEMINI]     contents=types.Content(role="user", parts=[types.Part(text=f"Task: {task}")]),
        # [GEMINI]     config=types.GenerateContentConfig(system_instruction=_SYSTEM_PROMPT, temperature=0.1, max_output_tokens=256),
        # [GEMINI] )
        # [GEMINI] cmd = (resp.text or "").strip().strip("`").strip()
        try:
            # [GROQ]
            cmd = await generate_text(
                system=_SYSTEM_PROMPT,
                user=f"Task: {task}",
                temperature=0.1,
                max_tokens=256,
            )
            cmd = cmd.strip().strip("`").strip()
            if not cmd or cmd == "CANNOT_EXECUTE":
                return None
            return cmd
        except Exception as exc:
            print(f"[cli] command generation failed: {exc}")
            return None

    async def execute(self, task: str, timeout: int = 30, **_) -> dict:
        """Generate and run a shell command for the task."""
        cmd = await self._generate_command(task)

        if not cmd:
            return {
                "success": False,
                "result": None,
                "error": f"Could not generate a shell command for: {task}",
            }

        # Safety check
        if any(blocked in cmd for blocked in _BLOCKED):
            return {
                "success": False,
                "result": None,
                "error": f"Command blocked for safety: {cmd}",
            }

        print(f"[cli] running: {cmd}")

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            out = stdout.decode("utf-8", errors="replace").strip()
            err = stderr.decode("utf-8", errors="replace").strip()

            if proc.returncode == 0:
                return {
                    "success": True,
                    "result": out or f"Done: {cmd}",
                    "error": None,
                }
            else:
                return {
                    "success": False,
                    "result": out or None,
                    "error": err or f"Command exited with code {proc.returncode}",
                }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "result": None,
                "error": f"Command timed out after {timeout}s: {cmd}",
            }
        except Exception as exc:
            return {
                "success": False,
                "result": None,
                "error": str(exc),
            }

    async def run_command(self, command: str, timeout: int = 30) -> tuple[str, str, int]:
        """Run a shell command directly (bypasses LLM)."""
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return (
                stdout.decode("utf-8", errors="replace"),
                stderr.decode("utf-8", errors="replace"),
                proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return "", "Command timed out", -1
