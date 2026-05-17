from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView


class IsOwner(permissions.BasePermission):
    """
    Object-level permission — only the owner of an object may access it.

    has_permission is checked on every request (including list/create).
    has_object_permission is checked on detail views only (retrieve/update/destroy).

    Because get_queryset() already filters by owner, a non-owner never even
    sees an object — they get a 404. has_object_permission is a second layer
    of defence in case get_queryset() is bypassed (e.g. in tests or admin).
    """

    message = "You do not have permission to access this resource."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(
        self, request: Request, view: APIView, obj: object
    ) -> bool:
        return hasattr(obj, "owner") and obj.owner == request.user  # type: ignore[attr-defined]
