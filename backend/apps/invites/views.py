from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.invites.serializers import InviteSerializer
from apps.invites.services.invite import accept_invite


class InviteAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, code):
        result = accept_invite(user=request.user, code=code)

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
