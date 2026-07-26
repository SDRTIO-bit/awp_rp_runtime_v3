"""Novel and shared memory contracts.

Import contracts from their focused modules to keep package import free of
unrelated runtime dependencies.
"""

from .novel_authoring import (
    AuthorApproval,
    AuthorChapterPlan,
    AuthorCharacterIntent,
    AuthorMaterial,
    AuthorPlanStatus,
    AuthorScene,
)
from .novel_web_event import NovelRoomId, NovelWebEvent
from .novel_document import NovelDocumentKind, NovelDocumentVersion
from .novel_prompt_version import (
    NovelPromptSnapshot,
    NovelPromptVersion,
    PromptRole,
    ResolvedPrompt,
)

__all__ = [
    "AuthorApproval",
    "AuthorChapterPlan",
    "AuthorCharacterIntent",
    "AuthorMaterial",
    "AuthorPlanStatus",
    "AuthorScene",
    "NovelRoomId",
    "NovelWebEvent",
    "NovelDocumentKind",
    "NovelDocumentVersion",
    "NovelPromptSnapshot",
    "NovelPromptVersion",
    "PromptRole",
    "ResolvedPrompt",
]
