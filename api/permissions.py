from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to access or edit it.
    """
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Allows read permissions to any request (GET, HEAD, OPTIONS),
    while restricting write permissions (POST, PUT, PATCH, DELETE) to staff/admins.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)

