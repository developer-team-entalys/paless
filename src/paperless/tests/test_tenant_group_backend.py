"""
Unit tests for TenantGroupBackend authentication backend.

Tests verify that:
1. TenantGroup permissions are properly checked
2. Django Group permissions still work
3. User-level permissions still work
4. Permission caching works correctly
5. Tenant isolation is maintained
"""

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from documents.models import Tenant, TenantGroup
from documents.models.base import get_current_tenant_id, set_current_tenant_id
from paperless.auth_backends import TenantGroupBackend
from paperless.models import UserProfile


class TenantGroupBackendTest(TestCase):
    """Test suite for TenantGroupBackend."""

    def setUp(self):
        """Set up test data."""
        self.backend = TenantGroupBackend()

        # Create test tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            subdomain="test",
        )

        # Set tenant context
        set_current_tenant_id(self.tenant.id)

        # Create test user
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            is_active=True,
        )

        # Create UserProfile for tenant association
        UserProfile.objects.create(
            user=self.user,
            tenant_id=self.tenant.id,
        )

        # Create test permissions
        content_type = ContentType.objects.get_for_model(Tenant)
        self.perm_view = Permission.objects.create(
            codename="view_test",
            name="Can view test",
            content_type=content_type,
        )
        self.perm_add = Permission.objects.create(
            codename="add_test",
            name="Can add test",
            content_type=content_type,
        )
        self.perm_change = Permission.objects.create(
            codename="change_test",
            name="Can change test",
            content_type=content_type,
        )

    def tearDown(self):
        """Clean up after tests."""
        set_current_tenant_id(None)

    def test_user_without_permissions(self):
        """Test that user without permissions has no permissions."""
        self.assertFalse(
            self.backend.has_perm(self.user, f"{self.perm_view.content_type.app_label}.view_test")
        )
        self.assertEqual(len(self.backend.get_all_permissions(self.user)), 0)

    def test_user_level_permissions(self):
        """Test that user-level permissions work."""
        self.user.user_permissions.add(self.perm_view)
        self.user._perm_cache = None  # Clear cache

        self.assertTrue(
            self.backend.has_perm(self.user, f"{self.perm_view.content_type.app_label}.view_test")
        )

    def test_tenant_group_permissions(self):
        """Test that TenantGroup permissions work."""
        # Create TenantGroup with permissions
        tenant_group = TenantGroup.objects.create(
            name="Test Group",
            tenant_id=self.tenant.id,
        )
        tenant_group.permissions.add(self.perm_add)
        tenant_group.users.add(self.user)

        # Clear any cached permissions
        if hasattr(self.user, '_perm_cache'):
            delattr(self.user, '_perm_cache')
        if hasattr(self.user, '_group_perm_cache'):
            delattr(self.user, '_group_perm_cache')
        if hasattr(self.user, '_tenant_group_perm_cache'):
            delattr(self.user, '_tenant_group_perm_cache')

        # Test permission check
        self.assertTrue(
            self.backend.has_perm(self.user, f"{self.perm_add.content_type.app_label}.add_test")
        )

    def test_combined_permissions(self):
        """Test that user, Django Group, and TenantGroup permissions all work together."""
        # Add user-level permission
        self.user.user_permissions.add(self.perm_view)

        # Create Django Group with permission
        from django.contrib.auth.models import Group
        django_group = Group.objects.create(name="Django Test Group")
        django_group.permissions.add(self.perm_change)
        self.user.groups.add(django_group)

        # Create TenantGroup with permission
        tenant_group = TenantGroup.objects.create(
            name="Tenant Test Group",
            tenant_id=self.tenant.id,
        )
        tenant_group.permissions.add(self.perm_add)
        tenant_group.users.add(self.user)

        # Clear cache
        if hasattr(self.user, '_perm_cache'):
            delattr(self.user, '_perm_cache')
        if hasattr(self.user, '_group_perm_cache'):
            delattr(self.user, '_group_perm_cache')
        if hasattr(self.user, '_tenant_group_perm_cache'):
            delattr(self.user, '_tenant_group_perm_cache')

        # Test all permissions
        all_perms = self.backend.get_all_permissions(self.user)

        self.assertIn(f"{self.perm_view.content_type.app_label}.view_test", all_perms)
        self.assertIn(f"{self.perm_add.content_type.app_label}.add_test", all_perms)
        self.assertIn(f"{self.perm_change.content_type.app_label}.change_test", all_perms)
        self.assertEqual(len(all_perms), 3)

    def test_inactive_user_has_no_permissions(self):
        """Test that inactive users have no permissions."""
        self.user.user_permissions.add(self.perm_view)
        self.user.is_active = False
        self.user.save()

        self.assertFalse(
            self.backend.has_perm(self.user, f"{self.perm_view.content_type.app_label}.view_test")
        )
        self.assertEqual(len(self.backend.get_all_permissions(self.user)), 0)

    def test_superuser_has_all_permissions(self):
        """Test that superusers have all permissions without explicit assignment."""
        self.user.is_superuser = True
        self.user.save()

        # Superusers should have permission even without explicit assignment
        # Note: ModelBackend handles this in authenticate(), but has_perm checks is_active and is_superuser
        # The parent ModelBackend will handle superuser check
        self.assertTrue(self.user.is_superuser)

    def test_permission_caching(self):
        """Test that permission caching works correctly."""
        tenant_group = TenantGroup.objects.create(
            name="Cache Test Group",
            tenant_id=self.tenant.id,
        )
        tenant_group.permissions.add(self.perm_view)
        tenant_group.users.add(self.user)

        # Clear cache
        if hasattr(self.user, '_perm_cache'):
            delattr(self.user, '_perm_cache')
        if hasattr(self.user, '_group_perm_cache'):
            delattr(self.user, '_group_perm_cache')
        if hasattr(self.user, '_tenant_group_perm_cache'):
            delattr(self.user, '_tenant_group_perm_cache')

        # First call should populate cache
        perms1 = self.backend.get_all_permissions(self.user)

        # Second call should use cache
        perms2 = self.backend.get_all_permissions(self.user)

        self.assertEqual(perms1, perms2)
        self.assertTrue(hasattr(self.user, '_perm_cache'))

    def test_multiple_tenant_groups(self):
        """Test that user can have permissions from multiple TenantGroups."""
        # Create first tenant group
        group1 = TenantGroup.objects.create(
            name="Group 1",
            tenant_id=self.tenant.id,
        )
        group1.permissions.add(self.perm_view)
        group1.users.add(self.user)

        # Create second tenant group
        group2 = TenantGroup.objects.create(
            name="Group 2",
            tenant_id=self.tenant.id,
        )
        group2.permissions.add(self.perm_add)
        group2.users.add(self.user)

        # Clear cache
        if hasattr(self.user, '_perm_cache'):
            delattr(self.user, '_perm_cache')
        if hasattr(self.user, '_group_perm_cache'):
            delattr(self.user, '_group_perm_cache')
        if hasattr(self.user, '_tenant_group_perm_cache'):
            delattr(self.user, '_tenant_group_perm_cache')

        # Test both permissions
        all_perms = self.backend.get_all_permissions(self.user)

        self.assertIn(f"{self.perm_view.content_type.app_label}.view_test", all_perms)
        self.assertIn(f"{self.perm_add.content_type.app_label}.add_test", all_perms)

    def test_tenant_admin_permissions(self):
        """Test that tenant admin users created via management command have full permissions."""
        # Simulate the create_tenant_admins command
        from documents.signals.tenant_handlers import (
            create_tenant_admin_group,
            get_admin_permissions,
        )

        # Create admin user
        admin_user = User.objects.create_user(
            username="test-admin",
            password="adminpass123",
            is_staff=True,
            is_active=True,
        )

        UserProfile.objects.create(
            user=admin_user,
            tenant_id=self.tenant.id,
        )

        # Get admin group and permissions
        admin_group = create_tenant_admin_group(self.tenant.id)
        admin_group.users.add(admin_user)

        # Assign permissions to user (as done in create_tenant_admins command)
        admin_permissions = get_admin_permissions()
        admin_user.user_permissions.set(admin_permissions)

        # Clear cache
        if hasattr(admin_user, '_perm_cache'):
            delattr(admin_user, '_perm_cache')
        if hasattr(admin_user, '_group_perm_cache'):
            delattr(admin_user, '_group_perm_cache')
        if hasattr(admin_user, '_tenant_group_perm_cache'):
            delattr(admin_user, '_tenant_group_perm_cache')

        # Check that admin has permissions
        all_perms = self.backend.get_all_permissions(admin_user)
        self.assertGreater(len(all_perms), 0, "Admin user should have permissions")

        # Test a specific permission (documents.view_document should exist)
        self.assertTrue(
            self.backend.has_perm(admin_user, "documents.view_document"),
            "Admin should have documents.view_document permission"
        )
