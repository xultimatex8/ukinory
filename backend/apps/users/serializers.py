from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])


class ClaimGuestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True, validators=[validate_password])


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "username", "is_guest", "last_active_at")
