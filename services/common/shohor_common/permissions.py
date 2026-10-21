"""Role checks based on the `role` claim the auth service puts in every access token.

They work the same in the auth service (real User) and in every other service (stateless TokenUser),
because they only read the validated token.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from . import roles


def token_role(request):
    token = getattr(request, "auth", None)
    if token is None:
        return None
    try:
        return token.get("role")
    except AttributeError:
        return None


class HasRole(BasePermission):
    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        return token_role(request) in self.allowed_roles


class IsCustomer(HasRole):
    allowed_roles = (roles.CUSTOMER,)


class IsProvider(HasRole):
    allowed_roles = (roles.PROVIDER,)


class IsAdmin(HasRole):
    allowed_roles = (roles.ADMIN,)


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or token_role(request) == roles.ADMIN
