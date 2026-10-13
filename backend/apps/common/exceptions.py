from rest_framework import status
from rest_framework.exceptions import APIException


class QuotaExceeded(Exception):
    def __init__(self, client: str, period: str, limit: int) -> None:
        self.client = client
        self.period = period
        self.limit = limit
        super().__init__(
            f"Quota for '{client}' exceeded: limit of {limit} per {period}."
        )


class SessionNotFoundError(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Session not found."
    default_code = "session_not_found"
 
 
class NotSessionMemberError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You are not a member of this session."
    default_code = "not_session_member"
 
 
class SessionFullError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This session already has two participants."
    default_code = "session_full"
 
 
class SessionClosedError(APIException):
    status_code = status.HTTP_410_GONE
    default_detail = "This session is no longer available."
    default_code = "session_closed"
 
 
class SessionFinishedError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This session has already finished."
    default_code = "session_finished"
 
 
class SessionNotReadyError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The session is not ready yet."
    default_code = "session_not_ready"
 
 
class PartnerNotJoinedError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Your partner has not joined yet."
    default_code = "partner_not_joined"
 
 
class InvalidSessionStateError(APIException):
    """Operation not allowed in the session's current state (e.g. start twice)."""
 
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The session is not in a valid state for this action."
    default_code = "invalid_session_state"
