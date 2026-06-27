"""AWPV2WriterOutput — ComfyUI node for final writer output.

Extracts the final player-visible text from WriterDraft.
"""

from __future__ import annotations


class AWPV2WriterOutput:
    """AWP V2 Writer输出节点"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "writer_draft": ("WRITER_DRAFT",),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("player_text",)
    FUNCTION = "execute"
    CATEGORY = "AWP V2 / Writer"

    def execute(self, writer_draft: dict):
        from ..contracts.writer_draft import WriterDraft

        draft = WriterDraft.from_dict(writer_draft)
        return (draft.text,)
