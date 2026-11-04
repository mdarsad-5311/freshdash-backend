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


class IsAdminRole(permissions.BasePermission):
    """
    Allows access only to authenticated administrative staff (admins or managers).
    Normal customers are strictly forbidden (HTTP 403).
    """
    message = "Access denied. Administrator privileges required."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser or user.is_staff:
            return True
        if hasattr(user, 'profile') and user.profile.role in ['admin', 'manager']:
            return True
        return False


