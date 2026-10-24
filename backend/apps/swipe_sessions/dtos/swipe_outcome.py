from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from apps.swipe_sessions.models import Swipe


@dataclass(slots=True)
class SwipeOutcome:
    swipe: "Swipe"
    created: bool = True
    match: Optional[dict] = None
