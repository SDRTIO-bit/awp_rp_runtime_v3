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

__all__ = [
    "AuthorApproval",
    "AuthorChapterPlan",
    "AuthorCharacterIntent",
    "AuthorMaterial",
    "AuthorPlanStatus",
    "AuthorScene",
    "NovelRoomId",
    "NovelWebEvent",
]
