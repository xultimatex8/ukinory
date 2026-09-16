from __future__ import annotations

import csv
import io

from apps.common.enums import SwipeAction
from apps.swipe_sessions.dtos.swipe_summary import SwipeExportSummary
from apps.swipe_sessions.models import Swipe


def export_watchlist_csv(user) -> SwipeExportSummary:
    swipes = (
        Swipe.objects.filter(user=user, action=SwipeAction.WATCHLIST)
        .select_related("candidate__movie")
        .order_by("-created_at")
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Title", "Year"])

    count = 0
    for swipe in swipes:
        movie = swipe.candidate.movie
        writer.writerow([movie.title, movie.release_year or ""])
        count += 1

    return SwipeExportSummary(rows_written=count, csv_content=buffer.getvalue())
