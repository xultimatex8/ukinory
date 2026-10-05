from apps.common.enums import InviteType


_handlers = {
    InviteType.COMPARISON: "accept_comparison_invite",
    InviteType.PAIRED_SWIPE: "accept_paired_swipe_invite",
}


def get_acceptance_handler(invite_type: str):
    try:
        return _handlers[invite_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported invite type: {invite_type}") from exc
    