"""Create RBAC groups and local demo users with API tokens."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand

from fleet.models import UserProfile
from prism_control.rbac import (
    ROLE_FLEET_ADMIN,
    ROLE_INSPECTOR,
    ROLE_VIEWER,
    ensure_role_groups,
)


class Command(BaseCommand):
    help = "Ensure viewer/inspector/fleet-admin groups and demo users exist"

    def handle(self, *args, **options):
        ensure_role_groups()
        password = settings.BOOTSTRAP_PASSWORD
        specs = [
            ("viewer", ROLE_VIEWER),
            ("inspector", ROLE_INSPECTOR),
            ("fleetadmin", ROLE_FLEET_ADMIN),
        ]
        for username, role in specs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"is_staff": role == ROLE_FLEET_ADMIN},
            )
            if created or not user.has_usable_password():
                user.set_password(password)
            if role == ROLE_FLEET_ADMIN:
                user.is_staff = True
            user.save()
            user.groups.set([Group.objects.get(name=role)])
            profile, _ = UserProfile.objects.get_or_create(user=user)
            self.stdout.write(
                self.style.SUCCESS(
                    f"{username}: role={role} token={profile.api_token} created={created}"
                )
            )

        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={"is_staff": True, "is_superuser": True},
        )
        if created or not admin_user.has_usable_password():
            admin_user.set_password(password)
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()
        profile, _ = UserProfile.objects.get_or_create(user=admin_user)
        self.stdout.write(
            self.style.SUCCESS(f"admin: superuser token={profile.api_token} created={created}")
        )
