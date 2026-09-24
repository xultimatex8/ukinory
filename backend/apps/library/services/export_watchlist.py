from __future__ import annotations

import csv
import io


def watchlist_to_csv(user) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Title", "Year"])

    entries = (
        user.watchlist_entries
        .select_related("movie")
        .order_by("-added_date", "title")
    )

    for entry in entries:
        writer.writerow(
            [
                entry.title,
                entry.release_year or "",
            ]
        )

    return buffer.getvalue()
