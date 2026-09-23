import json

from django.contrib.auth import get_user_model
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.http import HttpResponse
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.legal.serializers import LegalDocumentsUnavailable
from apps.legal.exceptions import LegalAcceptanceError, LegalDocumentsUnavailableError
from apps.legal.services.accept import accept_current_documents

from .services.update_user import change_password, update_user
from .services.guest_claim import claim_guest
from .services.user_register import register_user
from .services.delete_account import delete_account
from .services.export_user_data import export_user_data

from .serializers import ChangePasswordSerializer, ClaimGuestSerializer, DeleteAccountSerializer, RegisterSerializer, UpdateUserSerializer, UserSerializer


User = get_user_model()


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


def _accept_legal_documents(user, documents):
    try:
        accept_current_documents(user, documents)
    except LegalAcceptanceError as exc:
        raise ValidationError({"accepted_documents": [str(exc)]})
    except LegalDocumentsUnavailableError:
        raise LegalDocumentsUnavailable()


class GuestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        user = User.objects.create_user(is_guest=True)
        return Response(
            {"user": UserSerializer(user).data, **_tokens_for_user(user)},
            status=status.HTTP_201_CREATED,
        )


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = dict(serializer.validated_data)
        documents = data.pop("accepted_documents")

        with transaction.atomic():
            user = register_user(**data)
            _accept_legal_documents(user, documents)

        return Response(
            {"user": UserSerializer(user).data, **_tokens_for_user(user)},
            status=status.HTTP_201_CREATED,
        )


class ClaimGuestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ClaimGuestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = dict(serializer.validated_data)
        documents = data.pop("accepted_documents")

        with transaction.atomic():
            user = claim_guest(request.user, **data)
            user.refresh_from_db()
            _accept_legal_documents(user, documents)

        return Response({"user": UserSerializer(user).data, **_tokens_for_user(user)})


class DeleteAccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        serializer = DeleteAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        delete_account(request.user, **serializer.validated_data)

        return Response({"detail": "Account successfully deleted!"})


class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            UserSerializer(request.user).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        if request.user.is_guest:
            return Response(
                {"detail": "Guest accounts cannot be edited. Claim your account first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = UpdateUserSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        user = update_user(
            request.user,
            **serializer.validated_data,
        )

        return Response(
            UserSerializer(user).data,
            status=status.HTTP_200_OK,
        )


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if request.user.is_guest:
            return Response(
                {
                    "detail": (
                        "Guest accounts cannot change their password. "
                        "Claim your account first."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        change_password(
            request.user,
            old_password=serializer.validated_data["old_password"],
            new_password=serializer.validated_data["new_password"],
        )

        return Response(
            {"detail": "Password successfully changed."},
            status=status.HTTP_200_OK,
        )


class ExportUserDataView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        data = export_user_data(request.user)
        payload = json.dumps(data, indent=2, ensure_ascii=False, cls=DjangoJSONEncoder)

        response = HttpResponse(payload, content_type="application/json")
        response["Content-Disposition"] = (
            f'attachment; filename="account-data-{request.user.pk}.json"'
        )
        return response
