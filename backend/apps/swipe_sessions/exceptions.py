from rest_framework import status
from rest_framework.exceptions import APIException, NotFound


class CandidateNotFoundError(NotFound):
    default_detail = "Candidate not found."
    default_code = "candidate_not_found"


class JustificationUnavailableError(Exception):
    """Control flow only: the view answers 200 with available=False."""


class PairedSessionRequiredError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "This action is only available in paired swipe sessions."
    default_code = "paired_session_required"


class PairedDataMissingError(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = (
        "Both of you need imported ratings before you can swipe together."
    )
    default_code = "paired_data_missing"
