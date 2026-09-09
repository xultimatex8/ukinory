from django.contrib.auth import get_user_model
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .services.guest_claim import claim_guest
from .services.user_register import register_user

from .serializers import ClaimGuestSerializer, RegisterSerializer, UserSerializer


User = get_user_model()


def _tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


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

        user = register_user(**serializer.validated_data)

        return Response(
            {"user": UserSerializer(user).data, **_tokens_for_user(user)},
            status=status.HTTP_201_CREATED,
        )


class ClaimGuestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ClaimGuestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = claim_guest(request.user, **serializer.validated_data)

        return Response({"user": UserSerializer(user).data, **_tokens_for_user(user)})
