"""AWPV2ToolTrace — ComfyUI node for tool execution trace output.

Outputs the tool execution trace for debugging and audit.
"""

from __future__ import annotations


class AWPV2ToolTrace:
    """AWP V2 工具追踪节点"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "execution_trace": ("EXECUTION_TRACE",),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("trace_json",)
    FUNCTION = "execute"
    CATEGORY = "AWP V2 / Tool Gateway"

    def execute(self, execution_trace: dict):
        import json
        return (json.dumps(execution_trace, ensure_ascii=False, indent=2),)
