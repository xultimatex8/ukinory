class InviteError(Exception):
    """Base exception for all invite operations."""


class InviteNotFoundError(InviteError):
    pass


class InviteAlreadyAcceptedError(InviteError):
    pass


class InviteExpiredError(InviteError):
    pass


class OwnInviteError(InviteError):
    pass


class TooManyPendingInvitesError(InviteError):
    pass
