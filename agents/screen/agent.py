"""
GhostOps Agent - Screen annotation and visual explanation.

This agent receives a screenshot and user query, then generates
timed annotations (boxes, text, pointers) to explain what's on screen.
"""
import copy
import io

from PIL import Image
from agents.screen.tools import SCREEN_TOOL_MAP, set_model_name
from agents.screen.prompts import SCREEN_SYSTEM_PROMPT


class ScreenAgent:
    """
    Screen annotation agent that draws visual explanations on the user's screen.

    Capable of:
    - Drawing bounding boxes around UI elements
    - Creating text labels and annotations
    - Drawing pointer dots with connecting lines
    - Timed sequences of annotations for explanations
    - Direct text responses for simple queries
    """

    def __init__(self, model_client=None, model_name: str = "gemini-2.5-flash", config=None):
        """
        Initialize the GhostOps agent.

        Args:
            model_client: Unused (kept for API compatibility)
            model_name: Logical model name (default: groq/llama-4-scout)
            config: Unused (kept for API compatibility)
        """
        self.model_name = model_name
        self.tool_map = SCREEN_TOOL_MAP

    async def execute(self, task: str, screenshot: Image = None) -> dict:
        """
        Execute a screen annotation task.

        Args:
            task: The user's query/request
            screenshot: PIL.Image of the current screen

        Returns:
            dict with keys:
                - success: bool
                - result: The model response
                - error: Optional error message if failed
        """
        try:
            await set_model_name(self.model_name)

            from core.provider import generate_vision_with_tools
            from agents.screen.tools import (
                draw_bounding_box_declaration,
                draw_point_declaration,
                create_text_declaration,
                direct_response_declaration,
                create_text_for_box_declaration,
                clear_screen_declaration,
                destroy_box_declaration,
                destroy_text_declaration,
            )

            # Use raw declaration dicts directly — gemini_provider handles conversion
            declarations = [
                copy.deepcopy(draw_bounding_box_declaration),
                copy.deepcopy(draw_point_declaration),
                copy.deepcopy(create_text_declaration),
                copy.deepcopy(direct_response_declaration),
                copy.deepcopy(create_text_for_box_declaration),
                copy.deepcopy(clear_screen_declaration),
                copy.deepcopy(destroy_box_declaration),
                copy.deepcopy(destroy_text_declaration),
            ]

            image_bytes = b""
            if screenshot:
                buf = io.BytesIO()
                screenshot.convert("RGB").save(buf, format="JPEG", quality=85)
                image_bytes = buf.getvalue()

            system_part = SCREEN_SYSTEM_PROMPT
            user_part = task

            tool_calls = await generate_vision_with_tools(
                system=system_part,
                user_text=user_part,
                image_bytes=image_bytes,
                tools=declarations,
            )

            for tc in tool_calls:
                fn_name = tc.get("name")
                fn_args = tc.get("args", {})
                print(f"\n[GhostOps] Function: {fn_name}")
                print(f"[GhostOps] Arguments: {fn_args}")
                tool = self.tool_map.get(fn_name)
                if tool:
                    tool(**fn_args)
                elif fn_name != "direct_response":
                    return {
                        "success": False,
                        "result": None,
                        "error": f"Unknown tool: {fn_name}"
                    }

            return {
                "success": True,
                "result": tool_calls,
                "error": None
            }

        except Exception as e:
            return {
                "success": False,
                "result": None,
                "error": str(e)
            }
