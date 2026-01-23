"""
Custom authentication backends for Paperless.

This module provides authentication backends that extend Django's default
ModelBackend to support multi-tenant permission checking via TenantGroup.
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission


class TenantGroupBackend(ModelBackend):
    """
    Custom authentication backend that checks TenantGroup permissions.

    This backend extends Django's ModelBackend to support permission checking
    for the custom TenantGroup model, which provides tenant-scoped groups with
    their own permissions.

    Permission Resolution Order:
    1. User-level permissions (user.user_permissions)
    2. Standard Django Group permissions (user.groups)
    3. TenantGroup permissions (user.tenant_groups)

    This backend works alongside Django's ModelBackend to provide full
    permission support for both standard Django groups and tenant-scoped groups.
    """

    def _get_tenant_group_permissions(self, user_obj):
        """
        Get permissions from TenantGroup memberships.

        Args:
            user_obj: Django User instance

        Returns:
            QuerySet of Permission objects from all TenantGroups the user belongs to
        """
        if not hasattr(user_obj, '_tenant_group_perm_cache'):
            if user_obj.is_active and not user_obj.is_anonymous:
                # Import here to avoid circular imports
                from documents.models import TenantGroup

                # Get all tenant groups this user belongs to
                tenant_group_ids = user_obj.tenant_groups.values_list('id', flat=True)

                # Get all permissions from those groups
                perms = Permission.objects.filter(
                    tenantgroup__id__in=tenant_group_ids
                ).distinct()

                user_obj._tenant_group_perm_cache = perms
            else:
                user_obj._tenant_group_perm_cache = Permission.objects.none()

        return user_obj._tenant_group_perm_cache

    def _get_group_permissions(self, user_obj):
        """
        Override to include both Django Group and TenantGroup permissions.

        This method combines:
        - Standard Django Group permissions (via super())
        - Custom TenantGroup permissions (via _get_tenant_group_permissions)

        Args:
            user_obj: Django User instance

        Returns:
            QuerySet of Permission objects
        """
        # Get standard group permissions from parent class
        django_group_perms = super()._get_group_permissions(user_obj)

        # Get tenant group permissions
        tenant_group_perms = self._get_tenant_group_permissions(user_obj)

        # Combine both querysets
        return django_group_perms | tenant_group_perms

    def get_group_permissions(self, user_obj, obj=None):
        """
        Return a set of permission strings the user has from their groups.

        This includes both Django Groups and TenantGroups.

        Args:
            user_obj: Django User instance
            obj: Optional object for object-level permissions (not used here)

        Returns:
            Set of permission strings in format "app_label.codename"
        """
        if not hasattr(user_obj, '_group_perm_cache'):
            permissions = self._get_group_permissions(user_obj)
            user_obj._group_perm_cache = {
                f"{perm.content_type.app_label}.{perm.codename}"
                for perm in permissions
            }
        return user_obj._group_perm_cache

    def get_all_permissions(self, user_obj, obj=None):
        """
        Return a set of permission strings the user has.

        This includes:
        - User-level permissions (user.user_permissions)
        - Django Group permissions
        - TenantGroup permissions

        Args:
            user_obj: Django User instance
            obj: Optional object for object-level permissions (not used here)

        Returns:
            Set of permission strings in format "app_label.codename"
        """
        if not user_obj.is_active:
            return set()

        if not hasattr(user_obj, '_perm_cache'):
            # Get user permissions
            user_obj._perm_cache = {
                f"{perm.content_type.app_label}.{perm.codename}"
                for perm in user_obj.user_permissions.select_related('content_type')
            }
            # Add group permissions (includes both Django Group and TenantGroup)
            user_obj._perm_cache.update(self.get_group_permissions(user_obj))

        return user_obj._perm_cache

    def has_perm(self, user_obj, perm, obj=None):
        """
        Check if user has a specific permission.

        This method checks:
        1. Superuser status (has all permissions)
        2. User-level permissions
        3. Django Group permissions
        4. TenantGroup permissions

        Args:
            user_obj: Django User instance
            perm: Permission string in format "app_label.codename"
            obj: Optional object for object-level permissions (not used here)

        Returns:
            Boolean indicating if user has the permission
        """
        if not user_obj.is_active:
            return False

        return perm in self.get_all_permissions(user_obj, obj)
