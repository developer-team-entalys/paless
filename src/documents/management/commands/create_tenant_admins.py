"""
Django management command to create admin users for tenants.

Usage:
    python manage.py create_tenant_admins              # Create for all tenants
    python manage.py create_tenant_admins --list       # List tenants and admin status
    python manage.py create_tenant_admins --tenant=acme # Create for specific tenant
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from documents.models import Tenant
from documents.models.base import get_current_tenant_id, set_current_tenant_id
from documents.signals.tenant_handlers import (
    create_tenant_admin_group,
    generate_secure_password,
)
from paperless.models import UserProfile


class Command(BaseCommand):
    help = 'Create admin users for tenants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all tenants with admin status',
        )
        parser.add_argument(
            '--tenant',
            type=str,
            help='Create admin for specific tenant (by subdomain)',
        )

    def handle(self, *args, **options):
        if options['list']:
            self.list_tenants()
        elif options['tenant']:
            self.create_for_tenant(options['tenant'])
        else:
            self.create_for_all_tenants()

    def list_tenants(self):
        """List all tenants with their admin user status."""
        self.stdout.write(self.style.SUCCESS("\n" + "="*80))
        self.stdout.write(self.style.SUCCESS("TENANT ADMIN STATUS"))
        self.stdout.write(self.style.SUCCESS("="*80))

        # Table header
        self.stdout.write(
            f"{'Subdomain':<20} {'Name':<30} {'Admin User':<20} {'Status':<10}"
        )
        self.stdout.write("-" * 80)

        tenants = Tenant.objects.all().order_by('subdomain')
        for tenant in tenants:
            admin_username = f"{tenant.subdomain}-admin"
            admin_exists = User.objects.filter(username=admin_username).exists()

            status = self.style.SUCCESS("✓ EXISTS") if admin_exists else self.style.WARNING("✗ MISSING")

            self.stdout.write(
                f"{tenant.subdomain:<20} {tenant.name:<30} {admin_username:<20} {status}"
            )

        self.stdout.write("="*80 + "\n")

    def create_for_tenant(self, subdomain):
        """Create admin user for a specific tenant."""
        try:
            tenant = Tenant.objects.get(subdomain=subdomain)
        except Tenant.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Tenant with subdomain '{subdomain}' not found")
            )
            return

        admin_username = f"{tenant.subdomain}-admin"

        if User.objects.filter(username=admin_username).exists():
            self.stdout.write(
                self.style.WARNING(f"Admin user '{admin_username}' already exists, skipping")
            )
            return

        password = self._create_admin_user(tenant)
        if password:
            self.stdout.write(
                self.style.SUCCESS(f"\n✓ Created admin user for tenant: {tenant.name}")
            )
            self._display_credentials(tenant, admin_username, password)

    def create_for_all_tenants(self):
        """Create admin users for all tenants that don't have one."""
        self.stdout.write(self.style.SUCCESS("\nCreating admin users for all tenants..."))

        tenants = Tenant.objects.all().order_by('subdomain')
        created_count = 0
        skipped_count = 0

        for tenant in tenants:
            admin_username = f"{tenant.subdomain}-admin"

            if User.objects.filter(username=admin_username).exists():
                self.stdout.write(
                    self.style.WARNING(f"✗ Skipped {tenant.subdomain}: Admin already exists")
                )
                skipped_count += 1
                continue

            password = self._create_admin_user(tenant)
            if password:
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created admin for {tenant.subdomain}")
                )
                self._display_credentials(tenant, admin_username, password)
                created_count += 1

        # Summary
        self.stdout.write("\n" + "="*80)
        self.stdout.write(
            self.style.SUCCESS(f"Summary: Created {created_count} admin user(s), skipped {skipped_count}")
        )
        self.stdout.write("="*80 + "\n")

    @transaction.atomic
    def _create_admin_user(self, tenant):
        """
        Create admin user for a tenant.

        Args:
            tenant: Tenant instance

        Returns:
            str: Generated password, or None if creation failed
        """
        admin_username = f"{tenant.subdomain}-admin"

        try:
            # Generate secure password
            password = generate_secure_password()

            # Create the admin user
            admin_user = User.objects.create_user(
                username=admin_username,
                email=f"{admin_username}@{tenant.subdomain}.local",
                password=password,
                is_staff=True,
                is_superuser=False
            )

            # Set tenant context and create UserProfile
            old_tenant_id = get_current_tenant_id()
            set_current_tenant_id(tenant.id)

            try:
                # Create UserProfile if it doesn't exist
                if not hasattr(admin_user, 'profile'):
                    UserProfile.objects.create(user=admin_user, tenant_id=tenant.id)

                # Create/get the Tenant Admin group with permissions
                admin_group = create_tenant_admin_group(tenant.id)

                # Add user to the admin group
                admin_group.users.add(admin_user)

            finally:
                set_current_tenant_id(old_tenant_id)

            return password

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to create admin for {tenant.subdomain}: {e}")
            )
            return None

    def _display_credentials(self, tenant, username, password):
        """Display admin credentials to stdout."""
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.WARNING("⚠️  TENANT ADMIN CREDENTIALS - SAVE SECURELY"))
        self.stdout.write("="*80)
        self.stdout.write(f"Tenant:   {tenant.name} ({tenant.subdomain})")
        self.stdout.write(f"Username: {username}")
        self.stdout.write(self.style.WARNING(f"Password: {password}"))
        self.stdout.write("="*80)
        self.stdout.write(self.style.WARNING("⚠️  This password will not be shown again!"))
        self.stdout.write("="*80 + "\n")
