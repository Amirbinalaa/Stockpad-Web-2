from rest_framework import permissions

class IsEngineer(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'engineer')

class IsWarehouseOrManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in ['warehouse', 'manager'])

class IsOwnerOrStaff(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role in ['warehouse', 'manager']:
            return True
        return obj.requested_by == request.user
