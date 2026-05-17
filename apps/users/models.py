import uuid

from django.contrib.auth.models import AbstractUser
from django.core.validators import URLValidator
from django.db import models


class User(AbstractUser):
    """
    Custom user model — always declared before the first migration.
    Referenced via AUTH_USER_MODEL = "users.User" in settings.

    AbstractUser provides: username, email, password, first_name, last_name,
    is_active, is_staff, is_superuser, last_login, date_joined, groups,
    user_permissions, and all auth methods (set_password, check_password, …).

    We add: UUID primary key, unique email, bio, avatar_url, created_at.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    bio = models.TextField(blank=True, default="")
    avatar_url = models.URLField(
        blank=True,
        default="",
        validators=[URLValidator()],
    )
    # auto_now_add: set once on INSERT, never updated
    created_at = models.DateTimeField(auto_now_add=True)

    REQUIRED_FIELDS = ["email"]

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return f"{self.username} <{self.email}>"


class UserProfile(models.Model):
    """
    One-to-one extension of User, created automatically via signal (signals.py).

    OneToOneField is a ForeignKey with unique=True; CASCADE means deleting the
    User also deletes the Profile. The related_name lets us do user.profile.
    JSONField (Django 3.1+) stores arbitrary preferences without extra tables.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    # Example keys: {"theme": "dark", "notifications": true, "timezone": "UTC"}
    preferences = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)  # set on every save

    class Meta:
        verbose_name = "user profile"
        verbose_name_plural = "user profiles"

    def __str__(self) -> str:
        return f"Profile of {self.user.username}"
