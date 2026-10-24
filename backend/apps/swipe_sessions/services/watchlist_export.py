from __future__ import annotations

from apps.common.enums import SwipeAction
from apps.library.services.watchlist import rows_to_csv
from apps.swipe_sessions.dtos.swipe_summary import SwipeExportSummary
from apps.swipe_sessions.models import Swipe


def export_watchlist_csv(user, session=None) -> SwipeExportSummary:
    swipes = (
        Swipe.objects.filter(user=user, action=SwipeAction.WATCHLIST)
        .select_related("candidate__movie")
        .order_by("-created_at")
    )

    if session is not None:
        swipes = swipes.filter(candidate__session=session)

    csv_content, count = rows_to_csv(
        (s.candidate.movie.title, s.candidate.movie.release_year) for s in swipes
    )
    return SwipeExportSummary(rows_written=count, csv_content=csv_content)
