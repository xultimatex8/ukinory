from rest_framework import status
from rest_framework.exceptions import APIException


class ComparisonNotFoundError(APIException):
    pass


class NotComparisonMemberError(Exception):
    pass


class InsufficientDataError(Exception):
    """A participant has no ratings, or the comparison is not 2-person."""


class RoomNotFoundError(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Comparison room not found."
    default_code = "room_not_found"


class NotRoomMemberError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You are not part of this room."
    default_code = "not_room_member"


class RoomFullError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This room already has two participants."
    default_code = "room_full"


class RoomClosedError(APIException):
    status_code = status.HTTP_410_GONE
    default_detail = "This room is no longer available."
    default_code = "room_closed"


class RoomNotReadyError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The comparison is not ready yet."
    default_code = "room_not_ready"


class RecommendationNotFoundError(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Recommendation not found."
    default_code = "recommendation_not_found"
