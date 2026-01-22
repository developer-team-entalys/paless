"""
Tests for create_tenant_admins management command.

Tests cover:
- --list mode (list all tenants with admin status)
- --tenant mode (create for specific tenant)
- Default mode (create for all tenants)
- Skipping existing admins
"""

from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from documents.models import Tenant
from documents.models.base import set_current_tenant_id


class CreateTenantAdminsCommandTestCase(TestCase):
    """Test create_tenant_admins management command."""

    def tearDown(self):
        """Clean up tenant context after each test."""
        set_current_tenant_id(None)

    def test_list_command(self):
        """Test that --list shows all tenants with their admin status."""
        # Create tenants (signal will create admins automatically)
        Tenant.objects.create(name="Alpha Corp", subdomain="alpha")
        Tenant.objects.create(name="Beta Inc", subdomain="beta")

        # Capture output
        out = StringIO()
        call_command('create_tenant_admins', '--list', stdout=out)
        output = out.getvalue()

        # Check output contains tenant info
        self.assertIn("alpha", output)
        self.assertIn("beta", output)
        self.assertIn("Alpha Corp", output)
        self.assertIn("Beta Inc", output)
        self.assertIn("EXISTS", output)  # Both should have admins via signal

    def test_create_for_specific_tenant(self):
        """Test that --tenant creates admin for specific tenant only."""
        # Create tenants but delete their auto-created admins
        tenant1 = Tenant.objects.create(name="Gamma LLC", subdomain="gamma")
        tenant2 = Tenant.objects.create(name="Delta Systems", subdomain="delta")

        # Delete the auto-created admins to test manual creation
        User.objects.filter(username="gamma-admin").delete()
        User.objects.filter(username="delta-admin").delete()

        # Create admin for gamma only
        out = StringIO()
        call_command('create_tenant_admins', '--tenant=gamma', stdout=out)
        output = out.getvalue()

        # Check gamma admin was created
        gamma_admin = User.objects.filter(username="gamma-admin").first()
        self.assertIsNotNone(gamma_admin, "Gamma admin should be created")
        self.assertIn("gamma", output)
        self.assertIn("Created admin", output)

        # Check delta admin was NOT created
        delta_admin = User.objects.filter(username="delta-admin").first()
        self.assertIsNone(delta_admin, "Delta admin should not be created")

    def test_create_for_all_tenants(self):
        """Test that default mode creates admins for all tenants without them."""
        # Create tenants but delete their auto-created admins
        Tenant.objects.create(name="Epsilon Corp", subdomain="epsilon")
        Tenant.objects.create(name="Zeta Ltd", subdomain="zeta")

        # Delete auto-created admins
        User.objects.filter(username="epsilon-admin").delete()
        User.objects.filter(username="zeta-admin").delete()

        # Run command without arguments
        out = StringIO()
        call_command('create_tenant_admins', stdout=out)
        output = out.getvalue()

        # Check both admins were created
        epsilon_admin = User.objects.filter(username="epsilon-admin").first()
        zeta_admin = User.objects.filter(username="zeta-admin").first()

        self.assertIsNotNone(epsilon_admin, "Epsilon admin should be created")
        self.assertIsNotNone(zeta_admin, "Zeta admin should be created")

        # Check output
        self.assertIn("epsilon", output)
        self.assertIn("zeta", output)
        self.assertIn("Summary", output)
        self.assertIn("Created 2", output)

    def test_skip_existing_admin(self):
        """Test that command skips tenants that already have admin users."""
        # Create tenant (admin created automatically via signal)
        tenant = Tenant.objects.create(name="Eta Enterprises", subdomain="eta")

        # Verify admin exists
        admin_exists = User.objects.filter(username="eta-admin").exists()
        self.assertTrue(admin_exists, "Admin should exist from signal")

        # Count admins before command
        admin_count_before = User.objects.filter(username="eta-admin").count()

        # Run command
        out = StringIO()
        call_command('create_tenant_admins', '--tenant=eta', stdout=out)
        output = out.getvalue()

        # Count admins after command
        admin_count_after = User.objects.filter(username="eta-admin").count()

        # Should still have only one admin
        self.assertEqual(admin_count_before, admin_count_after, "Should not create duplicate admin")
        self.assertEqual(admin_count_after, 1, "Should have exactly one admin")

        # Check output mentions skipping
        self.assertIn("already exists", output.lower())

    def test_command_with_nonexistent_tenant(self):
        """Test that --tenant with non-existent subdomain shows error."""
        out = StringIO()
        err = StringIO()
        call_command('create_tenant_admins', '--tenant=nonexistent', stdout=out, stderr=err)
        output = out.getvalue() + err.getvalue()

        # Should show error message
        self.assertIn("not found", output.lower())

    def test_command_displays_password(self):
        """Test that command displays generated password."""
        # Create tenant but delete auto-created admin
        Tenant.objects.create(name="Theta Partners", subdomain="theta")
        User.objects.filter(username="theta-admin").delete()

        # Run command
        out = StringIO()
        call_command('create_tenant_admins', '--tenant=theta', stdout=out)
        output = out.getvalue()

        # Should display credentials
        self.assertIn("theta-admin", output)
        self.assertIn("Password:", output)
        self.assertIn("SAVE SECURELY", output)
