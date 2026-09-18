from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists"
            )

        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "This username is already taken"
            )

        return value


class ClaimGuestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField(required=False)
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
    )

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "An account with this email already exists"
            )

        return value

    def validate_username(self, value):
        if value and User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "This username is already taken"
            )

        return value


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, required=False)


class UpdateUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField()

    def validate_email(self, value):
        user = self.context["request"].user

        if User.objects.filter(email__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError(
                "An account with this email already exists"
            )

        return value

    def validate_username(self, value):
        user = self.context["request"].user

        if User.objects.filter(username__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError(
                "This username is already taken"
            )

        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        write_only=True,
        required=True,
    )
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
    )

    def validate_old_password(self, value):
        user = self.context["request"].user

        if not user.check_password(value):
            raise serializers.ValidationError(
                "Your current password is incorrect"
            )

        return value


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "username", "is_guest")
