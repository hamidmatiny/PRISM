"""Print a bare bootstrap API token to stdout (no banners — safe for shell capture)."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from fleet.models import UserProfile


class Command(BaseCommand):
    help = (
        "Print only the api_token for a bootstrap user (default: viewer). "
        "Stdout is a single line with no Django shell banners — use for TOKEN=$(...)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            nargs="?",
            default="viewer",
            help="Bootstrap username (viewer|inspector|fleetadmin|admin)",
        )

    def handle(self, *args, **options):
        username = options["username"]
        try:
            user = User.objects.get(username=username)
            token = user.profile.api_token
        except User.DoesNotExist as exc:
            raise CommandError(
                f"user {username!r} not found — run migrate + bootstrap_rbac first"
            ) from exc
        except UserProfile.DoesNotExist as exc:
            raise CommandError(f"user {username!r} has no UserProfile / api_token") from exc
        # Bare token only — never style/wrap; scripts capture stdout.
        self.stdout.write(token)
