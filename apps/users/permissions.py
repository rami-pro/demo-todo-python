from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from .models import User


class IsSelfOrAdmin(permissions.BasePermission):
    """
    Object-level permission: allows users to manage only their own account,
    or staff/admins to manage any account.

    has_permission  → called on every request (list, create, …)
    has_object_permission → called only on detail views (retrieve, update, …)
    """

    message = "You do not have permission to access this resource."

    def has_permission(self, request: Request, view: APIView) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(
        self, request: Request, view: APIView, obj: object
    ) -> bool:
        if request.user.is_staff:
            return True
        return isinstance(obj, User) and obj == request.user
