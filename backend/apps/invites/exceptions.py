from rest_framework import status
from rest_framework.exceptions import APIException


class InviteError(APIException):
    """Base exception for all invite operations."""


class InviteNotFoundError(InviteError):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Invite not found."
    default_code = "invite_not_found"


class InviteAlreadyAcceptedError(InviteError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This invite has already been accepted."
    default_code = "invite_already_accepted"


class InviteExpiredError(InviteError):
    status_code = status.HTTP_410_GONE
    default_detail = "This invite has expired."
    default_code = "invite_expired"


class OwnInviteError(InviteError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "You cannot accept your own invite."
    default_code = "own_invite"


class TooManyPendingInvitesError(InviteError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "You have too many pending invites."
    default_code = "too_many_pending_invites"