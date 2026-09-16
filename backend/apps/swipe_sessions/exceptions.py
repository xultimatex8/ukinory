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


class SwipeSessionNotFoundError(RecommendationError):
    pass


class NotSessionMemberError(RecommendationError):
    pass


class SwipeSessionError(Exception):
    """Base exception for swipe session errors."""


class SwipeSessionNotFoundError(SwipeSessionError):
    pass


class NotSessionMemberError(SwipeSessionError):
    pass


class SwipeError(Exception):
    """Base exception for swipe operations."""


class CandidateNotFoundError(SwipeError):
    pass