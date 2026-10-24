from __future__ import annotations

from apps.library.models import Rating


def build_participant_state(session, user) -> dict:
    users = list(session.users.all())
    partner = next((u for u in users if u.pk != user.pk), None)
    with_data = set(
        Rating.objects.filter(user__in=users)
        .values_list("user_id", flat=True)
        .distinct()
    )

    return {
        "id": str(session.pk),
        "status": session.status,
        "participants": len(users),
        "partner_joined": partner is not None,
        "you_have_data": user.pk in with_data,
        "partner_has_data": (partner.pk in with_data) if partner else None,
    }
