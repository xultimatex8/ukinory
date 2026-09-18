from __future__ import annotations

from django.db.models import Count

from apps.swipe_sessions.models import SwipeSession


def delete_orphaned_sessions(session_ids=None):
    orphaned = SwipeSession.objects.annotate(users_count=Count("users")).filter(users_count=0)

    if session_ids is not None:
        if not session_ids:
            return 0, {}
        orphaned = orphaned.filter(pk__in=session_ids)

    return orphaned.delete()
