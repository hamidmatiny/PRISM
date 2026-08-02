"""RBAC helpers — viewer, inspector, fleet-admin enforced at the API layer."""

from __future__ import annotations

from django.contrib.auth.models import Group, User
from ninja.errors import HttpError
from ninja.security import HttpBearer

ROLE_VIEWER = "viewer"
ROLE_INSPECTOR = "inspector"
ROLE_FLEET_ADMIN = "fleet-admin"
ALL_ROLES = (ROLE_VIEWER, ROLE_INSPECTOR, ROLE_FLEET_ADMIN)


def ensure_role_groups() -> None:
    for name in ALL_ROLES:
        Group.objects.get_or_create(name=name)


def user_roles(user: User) -> set[str]:
    if not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set(ALL_ROLES)
    return set(user.groups.values_list("name", flat=True))


def user_has_role(user: User, *roles: str) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    owned = user_roles(user)
    return bool(owned.intersection(roles))


def assert_roles(request, *roles: str) -> User:
    """Raise 401/403 unless the authenticated user has one of ``roles``."""
    user = getattr(request, "auth", None) or getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        raise HttpError(401, "authentication required")
    if not user_has_role(user, *roles):
        raise HttpError(403, f"requires one of roles: {', '.join(roles)}")
    return user


class BearerAuth(HttpBearer):
    """Token auth via UserProfile.api_token."""

    def authenticate(self, request, token: str) -> User | None:
        from fleet.models import UserProfile

        try:
            profile = UserProfile.objects.select_related("user").get(api_token=token)
        except UserProfile.DoesNotExist:
            return None
        if not profile.user.is_active:
            return None
        request.user = profile.user
        return profile.user


auth = BearerAuth()
