from rest_framework import serializers

from apps.common.enums import InviteType
from apps.invites.models import Invite


class CreateInviteSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=InviteType.choices)


class InviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invite
        fields = ["id", "type", "status", "code", "expires_at", "accepted_at"]
        read_only_fields = ["id", "status", "code", "expires_at", "accepted_at"]
