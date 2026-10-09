from django.utils.module_loading import import_string

from apps.common.enums import InviteType

_handlers = {
    InviteType.COMPARISON: "apps.comparisons.services.invite_handler.accept_comparison_invite",
    InviteType.PAIRED_SWIPE: "apps.swipe_sessions.services.invite_handler.accept_paired_swipe_invite",
}


def get_acceptance_handler(invite_type: str):
    try:
        path = _handlers[invite_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported invite type: {invite_type}") from exc
    return import_string(path)