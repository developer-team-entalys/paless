"""
Tests for ProfileSerializer to ensure permissions are exposed to frontend.

This test ensures tenant admin users can see their permissions in the UI
by verifying that the /api/profile/ endpoint returns user_permissions and
inherited_permissions fields.
"""

import pytest
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient

from documents.models import Document, TenantGroup, Tenant
from documents.models.base import set_current_tenant_id
from paperless.models import UserProfile
from paperless.serialisers import ProfileSerializer


@pytest.mark.django_db
class TestProfileSerializerPermissions:
    """Test that ProfileSerializer includes permissions for frontend."""

    def test_profile_serializer_includes_user_permissions(self):
        """Test that ProfileSerializer includes user_permissions field."""
        user = User.objects.create_user(
            username="testuser",
            password="testpass",
            is_staff=True,
        )

        # Add some permissions to the user
        content_type = ContentType.objects.get_for_model(Document)
        perm_view = Permission.objects.get(
            content_type=content_type,
            codename="view_document",
        )
        perm_add = Permission.objects.get(
            content_type=content_type,
            codename="add_document",
        )
        user.user_permissions.add(perm_view, perm_add)

        # Serialize the user
        serializer = ProfileSerializer(user)
        data = serializer.data

        # Verify permissions are in the output
        assert "user_permissions" in data
        assert "inherited_permissions" in data
        assert "view_document" in data["user_permissions"]
        assert "add_document" in data["user_permissions"]

    def test_profile_serializer_includes_inherited_permissions(self):
        """Test that ProfileSerializer includes inherited_permissions from groups."""
        user = User.objects.create_user(
            username="testuser",
            password="testpass",
            is_staff=True,
        )

        # Create a group with permissions
        tenant = Tenant.objects.create(
            name="Test Tenant",
            subdomain="test",
        )
        set_current_tenant_id(tenant.id)

        group = TenantGroup.objects.create(name="Test Group", tenant_id=tenant.id)
        content_type = ContentType.objects.get_for_model(Document)
        perm_view = Permission.objects.get(
            content_type=content_type,
            codename="view_document",
        )
        group.permissions.add(perm_view)
        group.users.add(user)

        # Serialize the user
        serializer = ProfileSerializer(user)
        data = serializer.data

        # Verify inherited permissions are in the output
        assert "inherited_permissions" in data
        # inherited_permissions returns full permission names like 'documents.view_document'
        assert any("view_document" in perm for perm in data["inherited_permissions"])

    def test_profile_serializer_includes_tenant_group_permissions(self):
        """Test that ProfileSerializer includes permissions from TenantGroup."""
        # Create tenant
        tenant = Tenant.objects.create(
            name="Test Tenant",
            subdomain="test",
        )
        set_current_tenant_id(tenant.id)

        # Create user
        user = User.objects.create_user(
            username="testuser",
            password="testpass",
            is_staff=True,
        )
        UserProfile.objects.create(user=user, tenant_id=tenant.id)

        # Create TenantGroup with permissions
        tenant_group = TenantGroup.objects.create(name="Tenant Admin", tenant_id=tenant.id)
        content_type = ContentType.objects.get_for_model(Document)
        perm_view = Permission.objects.get(
            content_type=content_type,
            codename="view_document",
        )
        perm_add = Permission.objects.get(
            content_type=content_type,
            codename="add_document",
        )
        tenant_group.permissions.add(perm_view, perm_add)
        tenant_group.users.add(user)

        # Serialize the user
        serializer = ProfileSerializer(user)
        data = serializer.data

        # Verify TenantGroup permissions are in inherited_permissions
        assert "inherited_permissions" in data
        inherited = data["inherited_permissions"]
        assert "documents.view_document" in inherited
        assert "documents.add_document" in inherited

    def test_profile_api_endpoint_returns_permissions(self, client):
        """Integration test: /api/profile/ endpoint returns permissions."""
        # Create tenant
        tenant = Tenant.objects.create(
            name="Test Tenant",
            subdomain="test",
        )
        set_current_tenant_id(tenant.id)

        # Create user with permissions
        user = User.objects.create_user(
            username="testuser",
            password="testpass",
            is_staff=True,
        )
        UserProfile.objects.create(user=user, tenant_id=tenant.id)

        # Add permissions
        content_type = ContentType.objects.get_for_model(Document)
        perm_view = Permission.objects.get(
            content_type=content_type,
            codename="view_document",
        )
        perm_add = Permission.objects.get(
            content_type=content_type,
            codename="add_document",
        )
        user.user_permissions.add(perm_view, perm_add)

        # Login and call the profile endpoint
        api_client = APIClient()
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/profile/")

        # Verify response includes permissions
        assert response.status_code == 200
        assert "user_permissions" in response.data
        assert "inherited_permissions" in response.data
        assert "view_document" in response.data["user_permissions"]
        assert "add_document" in response.data["user_permissions"]

    def test_tenant_admin_has_all_permissions_in_profile(self, client):
        """Test that tenant admin created by management command has visible permissions."""
        # Create tenant
        tenant = Tenant.objects.create(
            name="ACME Corp",
            subdomain="acme",
        )
        set_current_tenant_id(tenant.id)

        # Create admin user (simulating create_tenant_admins command)
        admin_user = User.objects.create_user(
            username="acme-admin",
            password="testpass",
            is_staff=True,
            is_superuser=False,
        )
        UserProfile.objects.create(user=admin_user, tenant_id=tenant.id)

        # Add all document permissions (simulating admin permissions)
        content_type = ContentType.objects.get_for_model(Document)
        all_perms = Permission.objects.filter(content_type=content_type)
        admin_user.user_permissions.set(all_perms)

        # Serialize the admin user
        serializer = ProfileSerializer(admin_user)
        data = serializer.data

        # Verify admin has permissions visible
        assert "user_permissions" in data
        assert len(data["user_permissions"]) > 0
        assert "view_document" in data["user_permissions"]
        assert "add_document" in data["user_permissions"]
        assert "change_document" in data["user_permissions"]
        assert "delete_document" in data["user_permissions"]
