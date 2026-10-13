from rest_framework import status
from rest_framework.exceptions import APIException


class JustificationError(Exception):
    """Base exception for recommendation justification operations."""


class SwipeSessionNotFoundError(JustificationError):
    pass


class NotSessionMemberError(JustificationError):
    pass


class CandidateNotFoundError(JustificationError):
    pass


class RecommendationError(Exception):
    """Base exception for recommendation errors."""


class SwipeSessionError(Exception):
    """Base exception for all swipe session operations."""


class SwipeSessionNotFoundError(SwipeSessionError):
    pass


class NotSessionMemberError(SwipeSessionError):
    pass


class SwipeSessionFinishedError(SwipeSessionError):
    pass


class CandidateNotFoundError(SwipeSessionError):
    pass


class JustificationError(SwipeSessionError):
    """Errors specific to justification generation, still a session error."""


class JustificationUnavailableError(Exception):
    pass


class RecommendationError(SwipeSessionError):
    """Errors specific to recommendation retrieval, still a session error."""


class SwipeError(SwipeSessionError):
    """Errors specific to recording a swipe, still a session error."""


class PairedSessionRequiredError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This action is only available in paired swipe sessions."
    default_code = "paired_session_required"
 
 
class PairedSessionFullError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This session already has two participants."
    default_code = "paired_session_full"
 
 
class PairedSessionClosedError(APIException):
    status_code = status.HTTP_410_GONE
    default_detail = "This session is no longer available."
    default_code = "paired_session_closed"
 
 
class PartnerNotJoinedError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Your partner has not joined yet."
    default_code = "partner_not_joined"
 
 
class PairedDataMissingError(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = (
        "Both of you need imported ratings before you can swipe together."
    )
    default_code = "paired_data_missing"
 
 
class SessionNotStartedError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The session has not started yet."
    default_code = "session_not_started"