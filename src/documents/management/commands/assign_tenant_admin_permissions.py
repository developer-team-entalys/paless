import logging
from argparse import RawTextHelpFormatter

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

logger = logging.getLogger("paperless.management.tenant_admin_permissions")


class Command(BaseCommand):
    help = (
        "Assigns admin permissions to all tenant admin users.\n"
        "\n"
        "This command:\n"
        "  - Finds all users matching the pattern '{subdomain}-admin'\n"
        "  - Assigns all 60 admin permissions to each user\n"
        "  - Can be run multiple times safely (idempotent)\n"
        "\n"
        "Permissions assigned:\n"
        "  - Full CRUD (add, change, delete, view) for:\n"
        "    - Documents, Tags, Correspondents, Document Types\n"
        "    - Storage Paths, Saved Views, Notes, Share Links\n"
        "    - Custom Fields, Tenant Groups, Workflows, Users"
    )

    def create_parser(self, *args, **kwargs):
        parser = super().create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_arguments(self, parser):
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all tenant admin users and their permission counts without making changes'
        )

    def handle(self, *args, **options):
        # Import here to avoid circular imports
        from documents.signals.tenant_handlers import get_admin_permissions

        # Get all admin permissions
        admin_permissions = get_admin_permissions()

        if not admin_permissions:
            self.stdout.write(
                self.style.ERROR(
                    "Failed to retrieve admin permissions. "
                    "Check that all required models and permissions exist."
                )
            )
            return

        # Find all tenant admin users (pattern: {subdomain}-admin)
        admin_users = User.objects.filter(
            username__endswith='-admin',
            is_staff=True
        ).exclude(
            is_superuser=True  # Exclude global superusers
        )

        if not admin_users.exists():
            self.stdout.write(
                self.style.WARNING(
                    "No tenant admin users found matching pattern '{subdomain}-admin'"
                )
            )
            return

        # Handle --list option
        if options.get('list'):
            self.stdout.write(
                self.style.SUCCESS(
                    f"Found {len(admin_permissions)} admin permissions available"
                )
            )
            self.stdout.write(
                self.style.NOTICE(
                    f"Found {admin_users.count()} tenant admin users:\n"
                )
            )

            for user in admin_users:
                current_perms = user.user_permissions.count()
                status = "✓" if current_perms >= len(admin_permissions) else "✗"
                style = self.style.SUCCESS if current_perms >= len(admin_permissions) else self.style.ERROR

                self.stdout.write(
                    style(
                        f"  {status} {user.username}: {current_perms} permissions"
                    )
                )

            self.stdout.write(
                self.style.NOTICE(
                    f"\nRun without --list to assign permissions to users with missing permissions"
                )
            )
            return

        # Normal operation: assign permissions
        self.stdout.write(
            self.style.SUCCESS(
                f"Found {len(admin_permissions)} admin permissions to assign"
            )
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Found {admin_users.count()} tenant admin users to process"
            )
        )

        # Process each admin user
        updated_count = 0
        skipped_count = 0

        for user in admin_users:
            # Get current permission count
            current_perms = user.user_permissions.count()

            # Assign all admin permissions
            user.user_permissions.set(admin_permissions)

            # Get new permission count
            new_perms = user.user_permissions.count()

            if current_perms < new_perms:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ {user.username}: Updated permissions "
                        f"({current_perms} → {new_perms})"
                    )
                )
                updated_count += 1
            else:
                self.stdout.write(
                    self.style.NOTICE(
                        f"  {user.username}: Already has {current_perms} permissions (no change)"
                    )
                )
                skipped_count += 1

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'='*70}\n"
                f"Summary:\n"
                f"  Total users processed: {admin_users.count()}\n"
                f"  Users updated: {updated_count}\n"
                f"  Users already correct: {skipped_count}\n"
                f"{'='*70}"
            )
        )

        if updated_count > 0:
            logger.info(
                f"Assigned admin permissions to {updated_count} tenant admin users"
            )
