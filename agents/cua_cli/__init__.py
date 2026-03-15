"""
CUA CLI Agent - Desktop control via Gemini CLI.

Wraps the gemini-cli (TypeScript/Node.js) to provide:
- Shell command execution
- File system operations
- Script execution
- CLI-based app control

The rapid response model invokes this agent for CLI tasks.
"""
from agents.cua_cli.agent import CLIAgent

__all__ = ["CLIAgent"]
