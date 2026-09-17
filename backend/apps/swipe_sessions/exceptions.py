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


class RecommendationError(SwipeSessionError):
    """Errors specific to recommendation retrieval, still a session error."""


class SwipeError(SwipeSessionError):
    """Errors specific to recording a swipe, still a session error."""
