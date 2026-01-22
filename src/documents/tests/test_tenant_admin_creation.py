"""
Tests for automatic tenant admin user creation.

Tests cover:
- Admin user creation when tenant is created
- UserProfile creation and linking
- Tenant group membership
- Permission assignment
- Duplicate prevention
- Multi-tenant isolation
- User flags (is_staff, is_superuser)
"""

from django.contrib.auth.models import User
from django.test import TestCase

from documents.models import Tenant, TenantGroup
from documents.models.base import set_current_tenant_id
from paperless.models import UserProfile


class TenantAdminCreationTestCase(TestCase):
    """Test automatic tenant admin user creation via signals."""

    def tearDown(self):
        """Clean up tenant context after each test."""
        set_current_tenant_id(None)

    def test_admin_user_created_on_tenant_creation(self):
        """Test that admin user is automatically created when tenant is created."""
        tenant = Tenant.objects.create(
            name="Test Company",
            subdomain="testco"
        )

        # Admin user should exist
        admin_username = f"{tenant.subdomain}-admin"
        admin_user = User.objects.filter(username=admin_username).first()

        self.assertIsNotNone(admin_user, "Admin user should be created")
        self.assertEqual(admin_user.username, "testco-admin")
        self.assertEqual(admin_user.email, "testco-admin@testco.local")

    def test_admin_user_has_user_profile(self):
        """Test that admin user has a UserProfile linked to the tenant."""
        tenant = Tenant.objects.create(
            name="ACME Corp",
            subdomain="acme"
        )

        admin_username = f"{tenant.subdomain}-admin"
        admin_user = User.objects.get(username=admin_username)

        # UserProfile should exist and be linked to the tenant
        self.assertTrue(hasattr(admin_user, 'profile'), "Admin user should have a profile")
        self.assertEqual(admin_user.profile.tenant_id, tenant.id)

    def test_admin_user_in_tenant_group(self):
        """Test that admin user is added to the Tenant Admin group."""
        tenant = Tenant.objects.create(
            name="Beta Inc",
            subdomain="beta"
        )

        admin_username = f"{tenant.subdomain}-admin"
        admin_user = User.objects.get(username=admin_username)

        # Set tenant context to query tenant groups
        set_current_tenant_id(tenant.id)

        # Admin user should be in Tenant Admin group
        admin_group = TenantGroup.objects.filter(name="Tenant Admin").first()
        self.assertIsNotNone(admin_group, "Tenant Admin group should exist")
        self.assertIn(admin_user, admin_group.users.all(), "Admin user should be in Tenant Admin group")

    def test_admin_group_has_permissions(self):
        """Test that Tenant Admin group has appropriate permissions."""
        tenant = Tenant.objects.create(
            name="Gamma LLC",
            subdomain="gamma"
        )

        # Set tenant context to query tenant groups
        set_current_tenant_id(tenant.id)

        admin_group = TenantGroup.objects.filter(name="Tenant Admin").first()
        self.assertIsNotNone(admin_group, "Tenant Admin group should exist")

        # Group should have permissions
        permissions = admin_group.permissions.all()
        self.assertGreater(
            len(permissions),
            0,
            "Tenant Admin group should have permissions"
        )

        # Check for some key permissions
        permission_codenames = [p.codename for p in permissions]
        self.assertIn('view_document', permission_codenames)
        self.assertIn('add_document', permission_codenames)
        self.assertIn('change_document', permission_codenames)

    def test_admin_user_has_permissions(self):
        """Test that admin user has permissions assigned DIRECTLY to user."""
        tenant = Tenant.objects.create(
            name="Test Org",
            subdomain="testorg"
        )
        admin_user = User.objects.get(username=f"{tenant.subdomain}-admin")

        # CRITICAL: Check user has DIRECT permissions (not just via group)
        user_perms = admin_user.user_permissions.all()
        self.assertGreater(
            user_perms.count(),
            50,
            "Admin user should have 56+ direct permissions"
        )

        # Verify Django's has_perm() works (this is what the app uses)
        self.assertTrue(
            admin_user.has_perm('documents.add_document'),
            "Admin should be able to add documents"
        )
        self.assertTrue(
            admin_user.has_perm('documents.change_document'),
            "Admin should be able to change documents"
        )
        self.assertTrue(
            admin_user.has_perm('documents.delete_document'),
            "Admin should be able to delete documents"
        )
        self.assertTrue(
            admin_user.has_perm('documents.view_document'),
            "Admin should be able to view documents"
        )
        self.assertTrue(
            admin_user.has_perm('documents.add_tag'),
            "Admin should be able to add tags"
        )
        self.assertTrue(
            admin_user.has_perm('auth.add_user'),
            "Admin should be able to add users"
        )

    def test_no_duplicate_admin_user(self):
        """Test that duplicate admin users are not created."""
        # Create tenant (admin user created via signal)
        tenant = Tenant.objects.create(
            name="Delta Systems",
            subdomain="delta"
        )

        admin_username = f"{tenant.subdomain}-admin"

        # Count initial admin users
        initial_count = User.objects.filter(username=admin_username).count()
        self.assertEqual(initial_count, 1, "Should have exactly one admin user")

        # Try to trigger signal again (save existing tenant)
        tenant.name = "Delta Systems Updated"
        tenant.save()

        # Should still have only one admin user
        final_count = User.objects.filter(username=admin_username).count()
        self.assertEqual(final_count, 1, "Should still have exactly one admin user")

    def test_admin_creation_for_different_tenants(self):
        """Test that multiple tenants get separate admin users."""
        tenant1 = Tenant.objects.create(
            name="Epsilon Corp",
            subdomain="epsilon"
        )
        tenant2 = Tenant.objects.create(
            name="Zeta Ltd",
            subdomain="zeta"
        )

        admin1 = User.objects.filter(username="epsilon-admin").first()
        admin2 = User.objects.filter(username="zeta-admin").first()

        self.assertIsNotNone(admin1, "Epsilon admin should exist")
        self.assertIsNotNone(admin2, "Zeta admin should exist")
        self.assertNotEqual(admin1.id, admin2.id, "Admin users should be different")

        # Check that profiles are linked to correct tenants
        self.assertEqual(admin1.profile.tenant_id, tenant1.id)
        self.assertEqual(admin2.profile.tenant_id, tenant2.id)

    def test_admin_is_staff_not_superuser(self):
        """Test that admin user has is_staff=True and is_superuser=False."""
        tenant = Tenant.objects.create(
            name="Eta Enterprises",
            subdomain="eta"
        )

        admin_username = f"{tenant.subdomain}-admin"
        admin_user = User.objects.get(username=admin_username)

        # Check flags
        self.assertTrue(admin_user.is_staff, "Admin should have is_staff=True")
        self.assertFalse(admin_user.is_superuser, "Admin should have is_superuser=False")

    def test_inactive_tenant_still_gets_admin(self):
        """Test that admin is created even for inactive tenants."""
        tenant = Tenant.objects.create(
            name="Theta Partners",
            subdomain="theta",
            is_active=False
        )

        admin_username = f"{tenant.subdomain}-admin"
        admin_user = User.objects.filter(username=admin_username).first()

        self.assertIsNotNone(admin_user, "Admin user should be created even for inactive tenants")
        self.assertEqual(admin_user.profile.tenant_id, tenant.id)
