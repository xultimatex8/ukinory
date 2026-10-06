from rest_framework import status
from rest_framework.exceptions import APIException


class ComparisonNotFoundError(APIException):
    pass


class NotComparisonMemberError(Exception):
    pass


class InsufficientDataError(Exception):
    """A participant has no ratings, or the comparison is not 2-person."""
