from rest_framework import serializers

from apps.common.enums import SwipeAction, SwipeSessionType
from apps.swipe_sessions.models import SwipeSession


class CreateSwipeSessionSerializer(serializers.Serializer):
    type = serializers.ChoiceField(
        choices=SwipeSessionType.choices,
    )


class SwipeSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SwipeSession
        fields = ["id", "type", "status"]


class SwipeSerializer(serializers.Serializer):
    candidate_id = serializers.UUIDField()
    action = serializers.ChoiceField(choices=SwipeAction.choices)