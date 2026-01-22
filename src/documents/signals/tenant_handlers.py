"""
Signal handlers for automatic tenant admin user creation.

This module provides:
- Automatic admin user creation when a tenant is created
- Secure password generation
- Admin group setup with full permissions
- Proper tenant context management
"""

import logging
import secrets
import string

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver

from documents.models import Tenant, TenantGroup
from documents.models.base import get_current_tenant_id, set_current_tenant_id
from paperless.models import UserProfile

logger = logging.getLogger("paperless.tenant_admin")


def generate_secure_password(length=16):
    """
    Generate a cryptographically secure random password.

    Args:
        length: Length of the password (default: 16)

    Returns:
        str: A secure random password containing letters, digits, and punctuation
    """
    alphabet = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


def get_admin_permissions():
    """
    Get all permissions needed for a tenant admin role.

    Returns:
        list: List of Permission objects for admin role
    """
    permissions = []

    # Define models and their app labels
    models_config = [
        # Documents app models
        ('documents', 'correspondent'),
        ('documents', 'tag'),
        ('documents', 'documenttype'),
        ('documents', 'document'),
        ('documents', 'storagepath'),
        ('documents', 'savedview'),
        ('documents', 'note'),
        ('documents', 'sharelink'),
        ('documents', 'customfield'),
        ('documents', 'customfieldinstance'),
        ('documents', 'tenantgroup'),
        ('documents', 'workflow'),
        ('documents', 'workflowtrigger'),
        ('documents', 'workflowaction'),
        # Auth app models for user management
        ('auth', 'user'),
    ]

    # Permission types
    permission_types = ['add', 'change', 'delete', 'view']

    for app_label, model in models_config:
        try:
            content_type = ContentType.objects.get(app_label=app_label, model=model)
            for perm_type in permission_types:
                try:
                    permission = Permission.objects.get(
                        content_type=content_type,
                        codename=f'{perm_type}_{model}'
                    )
                    permissions.append(permission)
                except Permission.DoesNotExist:
                    logger.warning(
                        f"Permission {perm_type}_{model} not found for {app_label}.{model}"
                    )
        except ContentType.DoesNotExist:
            logger.warning(f"ContentType not found for {app_label}.{model}")

    return permissions


def create_tenant_admin_group(tenant_id):
    """
    Create or get the "Tenant Admin" group for a tenant with full permissions.

    Args:
        tenant_id: UUID of the tenant

    Returns:
        TenantGroup: The created or existing admin group
    """
    old_tenant_id = get_current_tenant_id()
    set_current_tenant_id(tenant_id)

    try:
        # Get or create the Tenant Admin group
        admin_group, created = TenantGroup.objects.get_or_create(
            name="Tenant Admin",
            defaults={
                'tenant_id': tenant_id
            }
        )

        if created:
            logger.info(f"Created Tenant Admin group for tenant {tenant_id}")

        # Assign all admin permissions to the group
        admin_permissions = get_admin_permissions()
        admin_group.permissions.set(admin_permissions)

        logger.info(
            f"Assigned {len(admin_permissions)} permissions to Tenant Admin group "
            f"for tenant {tenant_id}"
        )

        return admin_group

    finally:
        set_current_tenant_id(old_tenant_id)


@receiver(post_save, sender=Tenant)
def create_tenant_admin_user(sender, instance, created, **kwargs):
    """
    Signal handler to automatically create an admin user when a tenant is created.

    This handler:
    - Creates a user with username "{subdomain}-admin"
    - Generates a secure random password
    - Sets is_staff=True (for Django admin access) and is_superuser=False (tenant-scoped)
    - Creates a UserProfile linked to the tenant
    - Creates "Tenant Admin" group with full permissions
    - Adds the user to the admin group
    - Logs the password to the console

    Args:
        sender: The Tenant model class
        instance: The Tenant instance being saved
        created: Boolean indicating if this is a new tenant
        **kwargs: Additional keyword arguments
    """
    if not created:
        # Only create admin for new tenants
        return

    username = f"{instance.subdomain}-admin"

    # Defensive check: skip if admin user already exists
    if User.objects.filter(username=username).exists():
        logger.info(f"Admin user {username} already exists, skipping creation")
        return

    # Generate secure password
    password = generate_secure_password()

    # Create the admin user
    admin_user = User.objects.create_user(
        username=username,
        email=f"{username}@{instance.subdomain}.local",
        password=password,
        is_staff=True,  # Django admin access
        is_superuser=False  # Tenant-scoped only
    )

    logger.info(f"Created admin user: {username} for tenant {instance.subdomain}")

    # Set tenant context and create UserProfile
    old_tenant_id = get_current_tenant_id()
    set_current_tenant_id(instance.id)

    try:
        # Ensure UserProfile is created (may already exist from signal)
        if not hasattr(admin_user, 'profile'):
            UserProfile.objects.create(user=admin_user, tenant_id=instance.id)
            logger.info(f"Created UserProfile for {username} with tenant {instance.id}")

        # Create the Tenant Admin group with permissions
        admin_group = create_tenant_admin_group(instance.id)

        # Add user to the admin group
        admin_group.users.add(admin_user)
        logger.info(f"Added {username} to Tenant Admin group")

        # CRITICAL FIX: Also assign permissions directly to user
        # Django's ModelBackend doesn't check TenantGroup, only user.user_permissions
        admin_permissions = get_admin_permissions()
        admin_user.user_permissions.set(admin_permissions)
        logger.info(f"Assigned {len(admin_permissions)} permissions directly to {username}")

    finally:
        set_current_tenant_id(old_tenant_id)

    # Log password to console with clear warning
    logger.warning(
        f"\n"
        f"{'='*70}\n"
        f"TENANT ADMIN CREDENTIALS - SAVE SECURELY\n"
        f"{'='*70}\n"
        f"Tenant: {instance.name} ({instance.subdomain})\n"
        f"Username: {username}\n"
        f"Password: {password}\n"
        f"{'='*70}\n"
        f"This password will not be shown again!\n"
        f"{'='*70}\n"
    )
