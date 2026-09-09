import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models

from apps.common.models import BaseModel


class UserManager(BaseUserManager):
    def create_user(self, email=None, username=None, password=None, is_guest=False, **extra_fields):
        if not is_guest and not email:
            raise ValueError("Email is mandatory for non-guest users")

        if email:
            email = self.normalize_email(email)

        if not username:
            username = self._generate_guest_username()

        user = self.model(
            email=email,
            username=username,
            is_guest=is_guest,
            **extra_fields,
        )

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(
            email=email,
            username=username,
            password=password,
            is_guest=False,
            **extra_fields,
        )

    @staticmethod
    def _generate_guest_username():
        return f"guest_{uuid.uuid4().hex[:10]}"


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, null=True, blank=True)
    username = models.CharField(max_length=150, unique=True)
    is_guest = models.BooleanField(default=False)
    last_active_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(is_guest=False) | models.Q(email__isnull=True),
                name="guest_users_have_no_email",
            ),
        ]

    def __str__(self):
        return self.username
