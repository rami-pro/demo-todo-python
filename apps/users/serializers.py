from rest_framework import serializers

from .models import User, UserProfile


class UserProfileSerializer(serializers.ModelSerializer[UserProfile]):
    class Meta:
        model = UserProfile
        fields = ["preferences", "updated_at"]
        read_only_fields = ["updated_at"]


class UserSerializer(serializers.ModelSerializer[User]):
    """
    Demonstrates several DRF serializer patterns:
    - Nested serializer: `profile` reads the related UserProfile row.
    - SerializerMethodField: `todo_count` is computed, not a DB column.
    - write_only=True: `password` is accepted on input but never returned.
    - read_only_fields: `id` and `created_at` can never be set by the client.
    """

    profile = UserProfileSerializer(read_only=True)
    todo_count = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "bio",
            "avatar_url",
            "created_at",
            "password",
            "profile",
            "todo_count",
        ]
        read_only_fields = ["id", "created_at"]

    def get_todo_count(self, obj: User) -> int:
        """Method names for SerializerMethodField must be get_<field_name>."""
        return obj.todos.count()  # type: ignore[attr-defined]

    def create(self, validated_data: dict) -> User:  # type: ignore[override]
        password: str = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance: User, validated_data: dict) -> User:  # type: ignore[override]
        if password := validated_data.pop("password", None):
            instance.set_password(password)
        return super().update(instance, validated_data)


class UserRegistrationSerializer(serializers.ModelSerializer[User]):
    """
    Dedicated registration serializer — single-responsibility principle.
    Validates that both password fields match before creating the user.
    """

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "password_confirm"]

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data: dict) -> User:  # type: ignore[override]
        password: str = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
