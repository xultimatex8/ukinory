from rest_framework import status
from rest_framework.exceptions import APIException, NotFound


class ComparisonNotFoundError(NotFound):
    default_detail = "Comparison not found."
    default_code = "comparison_not_found"


class InsufficientDataError(APIException):
    """A participant has no ratings, or the comparison is not 2-person."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Not enough data to compare."
    default_code = "insufficient_data"


class RecommendationNotFoundError(NotFound):
    default_detail = "Recommendation not found."
    default_code = "recommendation_not_found"
