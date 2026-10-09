from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.invites.exceptions import (
    InviteAlreadyAcceptedError,
    InviteExpiredError,
    InviteNotFoundError,
    OwnInviteError,
)
from apps.invites.serializers import (
    InviteSerializer,
)
from apps.invites.services.invite import (
    accept_invite,
)


class InviteAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, code):
        try:
            result = accept_invite(
                user=request.user,
                code=code,
            )
        except InviteNotFoundError:
            return Response(
                {"detail": "Invite not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except OwnInviteError:
            return Response(
                {"detail": "You cannot accept your own invite."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InviteAlreadyAcceptedError:
            return Response(
                {"detail": "This invite has already been accepted."},
                status=status.HTTP_409_CONFLICT,
            )
        except InviteExpiredError:
            return Response(
                {"detail": "This invite has expired."},
                status=status.HTTP_410_GONE,
            )

        return Response(
            {
                "invite": InviteSerializer(result.invite).data,
                "target": {
                    "id": result.target.pk,
                    "type": result.invite.type,
                },
            },
            status=status.HTTP_201_CREATED,
        )
