"""
Tests for assign_tenant_admin_permissions management command.

Tests cover:
- --list mode (list all tenant admin users with permission counts)
- Default mode (assign permissions to all tenant admins)
- Idempotency (running multiple times safely)
"""

from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from documents.models import Tenant
from documents.models.base import set_current_tenant_id


class AssignTenantAdminPermissionsCommandTestCase(TestCase):
    """Test assign_tenant_admin_permissions management command."""

    def tearDown(self):
        """Clean up tenant context after each test."""
        set_current_tenant_id(None)

    def test_list_shows_all_admins_with_permission_counts(self):
        """Test that --list displays all tenant admin users with permission counts."""
        # Create tenants (signal creates admins automatically with permissions)
        Tenant.objects.create(name="Alpha Corp", subdomain="alpha")
        Tenant.objects.create(name="Beta Inc", subdomain="beta")

        # Run command with --list
        out = StringIO()
        call_command('assign_tenant_admin_permissions', '--list', stdout=out)
        output = out.getvalue()

        # Check output contains admin users
        self.assertIn("alpha-admin", output)
        self.assertIn("beta-admin", output)
        self.assertIn("60 permissions", output)  # Both should have all permissions
        self.assertIn("Found 60 admin permissions available", output)

    def test_list_shows_admins_without_permissions(self):
        """Test that --list identifies admins with missing permissions."""
        # Create tenant (admin created automatically)
        Tenant.objects.create(name="Gamma LLC", subdomain="gamma")

        # Remove permissions from admin
        gamma_admin = User.objects.get(username="gamma-admin")
        gamma_admin.user_permissions.clear()

        # Run command with --list
        out = StringIO()
        call_command('assign_tenant_admin_permissions', '--list', stdout=out)
        output = out.getvalue()

        # Check output shows admin with 0 permissions
        self.assertIn("gamma-admin", output)
        self.assertIn("0 permissions", output)

    def test_assign_permissions_to_all_admins(self):
        """Test that default mode assigns permissions to all tenant admins."""
        # Create tenant and admin
        Tenant.objects.create(name="Delta Systems", subdomain="delta")
        delta_admin = User.objects.get(username="delta-admin")

        # Clear permissions to test assignment
        delta_admin.user_permissions.clear()
        self.assertEqual(delta_admin.user_permissions.count(), 0)

        # Run command without arguments
        out = StringIO()
        call_command('assign_tenant_admin_permissions', stdout=out)
        output = out.getvalue()

        # Check permissions were assigned
        delta_admin.refresh_from_db()
        self.assertEqual(delta_admin.user_permissions.count(), 60)
        self.assertIn("Updated permissions", output)
        self.assertIn("delta-admin", output)

    def test_command_is_idempotent(self):
        """Test that running command multiple times is safe."""
        # Create tenant (admin has permissions from signal)
        Tenant.objects.create(name="Epsilon Corp", subdomain="epsilon")
        epsilon_admin = User.objects.get(username="epsilon-admin")

        # Run command once
        out1 = StringIO()
        call_command('assign_tenant_admin_permissions', stdout=out1)

        # Check permissions count
        perm_count_after_first = epsilon_admin.user_permissions.count()
        self.assertEqual(perm_count_after_first, 60)

        # Run command again
        out2 = StringIO()
        call_command('assign_tenant_admin_permissions', stdout=out2)
        output2 = out2.getvalue()

        # Check permissions count didn't change
        epsilon_admin.refresh_from_db()
        perm_count_after_second = epsilon_admin.user_permissions.count()
        self.assertEqual(perm_count_after_second, 60)

        # Output should say no change needed
        self.assertIn("Already has", output2)

    def test_command_excludes_superusers(self):
        """Test that command excludes global superusers."""
        # Create superuser with -admin suffix
        User.objects.create_superuser(
            username="super-admin",
            email="super@admin.com",
            password="testpass"
        )

        # Run command with --list
        out = StringIO()
        call_command('assign_tenant_admin_permissions', '--list', stdout=out)
        output = out.getvalue()

        # super-admin should NOT be in the list
        self.assertNotIn("super-admin", output)

    def test_command_handles_no_admin_users(self):
        """Test command behavior when no tenant admin users exist."""
        # Delete all existing admin users
        User.objects.filter(username__endswith='-admin').delete()

        # Run command
        out = StringIO()
        call_command('assign_tenant_admin_permissions', '--list', stdout=out)
        output = out.getvalue()

        # Should show warning about no admins
        self.assertIn("No tenant admin users found", output)

    def test_assign_permissions_updates_count(self):
        """Test that permission count increases when assigning."""
        # Create tenant
        Tenant.objects.create(name="Zeta Ltd", subdomain="zeta")
        zeta_admin = User.objects.get(username="zeta-admin")

        # Clear permissions
        zeta_admin.user_permissions.clear()

        # Run command
        out = StringIO()
        call_command('assign_tenant_admin_permissions', stdout=out)
        output = out.getvalue()

        # Check output shows update from 0 to 60
        self.assertIn("zeta-admin", output)
        self.assertIn("0 → 60", output)
        self.assertIn("Users updated: 1", output)
