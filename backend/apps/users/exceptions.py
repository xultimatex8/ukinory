from rest_framework.exceptions import ValidationError


class UserRegistrationError(ValidationError):
    pass


class GuestClaimError(ValidationError):
    pass