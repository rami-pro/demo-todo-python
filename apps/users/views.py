from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from .models import User
from .permissions import IsSelfOrAdmin
from .serializers import UserRegistrationSerializer, UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    ModelViewSet bundles list, create, retrieve, update, partial_update,
    and destroy into one class. DRF Router auto-generates all URLs.

    Key patterns demonstrated:
    - get_permissions(): return different permission classes per action
    - get_serializer_class(): return different serializers per action
    - @action: adds extra endpoints beyond standard CRUD
    - select_related("profile"): avoids N+1 when serializing nested profiles
    """

    queryset = User.objects.select_related("profile").all()
    serializer_class = UserSerializer

    def get_permissions(self) -> list[permissions.BasePermission]:
        if self.action == "create":
            # Anyone can register
            return [permissions.AllowAny()]
        if self.action in ("list", "destroy"):
            # Only admins can list all users or delete arbitrary users
            return [permissions.IsAdminUser()]
        # Retrieve / update: only self or admin
        return [IsSelfOrAdmin()]

    def get_serializer_class(self):  # type: ignore[override]
        if self.action == "create":
            return UserRegistrationSerializer
        return UserSerializer

    @action(detail=False, methods=["get", "patch"], url_path="me")
    def me(self, request: Request) -> Response:
        """
        GET  /api/v1/users/me/ → return the authenticated user's own data
        PATCH /api/v1/users/me/ → partial update of the authenticated user

        Custom actions via @action avoid polluting the standard CRUD verbs.
        """
        if request.method == "GET":
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)

        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
