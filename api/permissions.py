from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrReadOnly(BasePermission):
    """
    Admins can do everything.
    Authenticated users can read.
    Anonymous users can read.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class IsAdminOnly(BasePermission):
    """Only admin/staff can access this endpoint at all."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff


class IsOwnerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        # Post -> user, LoveStory -> author, Celebrant -> created_by
        owner = getattr(obj, 'author', None) or getattr(obj, 'user', None) or getattr(obj, 'created_by', None)
        return owner == request.user