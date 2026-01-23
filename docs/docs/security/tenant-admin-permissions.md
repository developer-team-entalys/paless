---
sidebar_position: 3
title: Tenant Admin Permissions
description: Automatic tenant admin user creation and Django permissions architecture with TenantGroupBackend
keywords: [tenant admin, permissions, TenantGroup, authentication backend, TenantGroupBackend, Django permissions, user management, group permissions]
---

# Tenant Admin Permissions

## Overview

Paless automatically creates tenant administrator users when new tenants are provisioned. This document describes the permissions architecture, automatic user creation workflow, and the custom authentication backend that enables Django to recognize permissions from the `TenantGroup` model.

:::tip Key Takeaway
A custom `TenantGroupBackend` authentication backend extends Django's permission system to check both standard Django groups and the custom `TenantGroup` model, enabling tenant-scoped permission management.
:::

---

## Tenant Admin Creation

### Automatic Creation

When a new tenant is created, the system automatically provisions an admin user with full permissions:

```python
# Example: Creating tenant "acme"
tenant = Tenant.objects.create(name="Acme Corporation", subdomain="acme")

# Automatically creates:
# - Username: acme-admin
# - Password: [randomly generated, 16 characters]
# - Permissions: 60+ Django permissions for full access
```

**Triggers:**
1. **Signal Handler**: `post_save` signal on `Tenant` model (automatic)
2. **Management Command**: `python manage.py create_tenant_admins --tenant=acme` (manual)

### User Naming Convention

| Tenant Subdomain | Admin Username |
|------------------|----------------|
| `acme` | `acme-admin` |
| `globex` | `globex-admin` |
| `testcorp` | `testcorp-admin` |

---

## Permission Architecture

### Django's Permission System

Django's authentication system checks permissions using authentication backends. By default, Django uses `ModelBackend`, which checks:

```python
# Django's default ModelBackend checks:
1. user.user_permissions      # Direct user permissions ✅
2. user.groups                # Django's built-in Group model ✅
3. TenantGroup.permissions    # Custom model - NOT CHECKED by default ❌
```

### Custom Authentication Backend: TenantGroupBackend

**File:** `src/paperless/auth_backends.py`

Paless implements a custom `TenantGroupBackend` that extends Django's `ModelBackend` to include `TenantGroup` permissions:

```python
class TenantGroupBackend(ModelBackend):
    """
    Custom authentication backend that checks TenantGroup permissions.

    Permission Resolution Order:
    1. User-level permissions (user.user_permissions)
    2. Standard Django Group permissions (user.groups)
    3. TenantGroup permissions (user.tenant_groups)
    """
```

**Key Features:**

1. **Extends ModelBackend**: Maintains full compatibility with Django's standard permission system
2. **Multi-Source Permission Checking**: Combines permissions from:
   - User-level permissions (`user.user_permissions`)
   - Django Groups (`auth.Group`)
   - Tenant Groups (`TenantGroup`)
3. **Performance Optimized**: Uses Django's standard caching mechanism with three cache levels:
   - `_perm_cache`: All permissions (user + groups + tenant groups)
   - `_group_perm_cache`: Django Group + TenantGroup permissions
   - `_tenant_group_perm_cache`: TenantGroup permissions only
4. **Transparent Integration**: Works seamlessly with existing Django permission checks

### Configuration

**File:** `src/paperless/settings.py`

The backend is registered in Django settings:

```python
AUTHENTICATION_BACKENDS = [
    'guardian.backends.ObjectPermissionBackend',  # Object-level permissions
    'paperless.auth_backends.TenantGroupBackend',  # TenantGroup support
    'django.contrib.auth.backends.ModelBackend',   # Standard Django permissions
]
```

**Order matters:** `TenantGroupBackend` is placed before `ModelBackend` to take precedence for permission checks.

### How Permission Resolution Works

When `user.has_perm('documents.view_document')` is called:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Django Permission Check Request                              │
│    user.has_perm('documents.view_document')                     │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Django Iterates Through AUTHENTICATION_BACKENDS              │
│    - Guardian backend (object permissions)                      │
│    - TenantGroupBackend ✨                                      │
│    - ModelBackend (fallback)                                    │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. TenantGroupBackend.has_perm() Checks:                       │
│    ✅ Is user active?                                           │
│    ✅ Is user superuser? (grants all permissions)               │
│    ✅ Does user have permission via user.user_permissions?      │
│    ✅ Does user have permission via auth.Group?                 │
│    ✅ Does user have permission via TenantGroup? ✨ NEW         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Result Cached for Performance                                │
│    - First call: ~5ms (database query)                          │
│    - Subsequent calls: <1ms (in-memory cache)                   │
└─────────────────────────────────────────────────────────────────┘
```

### Permission Assignment Strategy

The current implementation assigns permissions to `TenantGroup` for tenant-scoped permission management:

```python
# 1. Create TenantGroup with permissions
admin_group = create_tenant_admin_group(tenant.id)
admin_group.permissions.set(get_admin_permissions())

# 2. Add user to TenantGroup
admin_group.users.add(admin_user)

# 3. TenantGroupBackend automatically recognizes these permissions ✅
# No need to duplicate permissions to user.user_permissions
```

**Benefits:**

- **Centralized Management**: Permissions managed at group level, not per-user
- **Tenant Isolation**: TenantGroup inherits from `ModelWithOwner`, ensuring tenant-scoped groups
- **Scalability**: Easy to update permissions for all users in a group
- **Compatibility**: Works with Django's standard permission checking via custom backend

---

## Implementation Details

### Signal Handler

**File:** `src/documents/signals/tenant_handlers.py`

```python
@receiver(post_save, sender=Tenant)
def create_tenant_admin(sender, instance, created, **kwargs):
    """Automatically create admin user when tenant is created."""

    if not created:
        return

    try:
        # Generate secure random password
        password = generate_secure_password()

        # Create admin user
        username = f"{instance.subdomain}-admin"
        admin_user = User.objects.create_user(
            username=username,
            password=password,
            is_staff=True,
        )

        # Create UserProfile with tenant association
        UserProfile.objects.create(user=admin_user, tenant_id=instance.id)

        # Create TenantGroup and assign permissions
        admin_group = create_tenant_admin_group(instance.id)
        admin_group.users.add(admin_user)

        # Permissions are automatically recognized via TenantGroupBackend
        logger.info(f"Created admin user: {username}")
        logger.info(f"Added {username} to TenantGroup with {admin_group.permissions.count()} permissions")

    finally:
        set_current_tenant_id(old_tenant_id)
```

**Lines:** 197-201 in `tenant_handlers.py:197-201`

### Management Command

**File:** `src/documents/management/commands/create_tenant_admins.py`

The management command provides a way to manually create or recreate tenant admin users:

```bash
# Create admin for specific tenant
python manage.py create_tenant_admins --tenant=acme

# Create admins for all tenants
python manage.py create_tenant_admins --all

# Recreate existing admin (replaces user)
python manage.py create_tenant_admins --tenant=acme --force
```

**Implementation:**

```python
class Command(BaseCommand):
    def handle(self, *args, **options):
        tenant = Tenant.objects.get(subdomain=options['tenant'])

        # Create user with tenant context
        old_tenant_id = get_current_tenant_id()
        set_current_tenant_id(tenant.id)

        try:
            # Create user and profile
            admin_user = User.objects.create_user(...)
            UserProfile.objects.create(user=admin_user, tenant_id=tenant.id)

            # Create group and assign permissions
            admin_group = create_tenant_admin_group(tenant.id)
            admin_group.users.add(admin_user)

            # Permissions are automatically recognized via TenantGroupBackend
            # No need to assign to user.user_permissions separately

        finally:
            set_current_tenant_id(old_tenant_id)
```

**Lines:** 171-174 in `create_tenant_admins.py:171-174`

---

## TenantGroupBackend Implementation

### Backend Architecture

**File:** `src/paperless/auth_backends.py`

The `TenantGroupBackend` class extends Django's `ModelBackend` with custom methods to retrieve and check TenantGroup permissions.

#### Method: `_get_tenant_group_permissions(user_obj)`

Retrieves permissions from all TenantGroups the user belongs to:

```python
def _get_tenant_group_permissions(self, user_obj):
    """Get permissions from TenantGroup memberships."""
    if not hasattr(user_obj, '_tenant_group_perm_cache'):
        if user_obj.is_active and not user_obj.is_anonymous:
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
```

**Key Points:**
- Caches results in `_tenant_group_perm_cache` to avoid repeated queries
- Only active, authenticated users receive permissions
- Uses `distinct()` to avoid duplicate permissions from multiple groups

#### Method: `_get_group_permissions(user_obj)`

Combines Django Group and TenantGroup permissions:

```python
def _get_group_permissions(self, user_obj):
    """Override to include both Django Group and TenantGroup permissions."""
    # Get standard group permissions from parent class
    django_group_perms = super()._get_group_permissions(user_obj)

    # Get tenant group permissions
    tenant_group_perms = self._get_tenant_group_permissions(user_obj)

    # Combine both querysets
    return django_group_perms | tenant_group_perms
```

**Key Points:**
- Calls parent `ModelBackend._get_group_permissions()` for Django Groups
- Adds TenantGroup permissions using QuerySet union
- Maintains backward compatibility with existing Django Groups

#### Method: `get_all_permissions(user_obj, obj=None)`

Returns all permissions from all sources:

```python
def get_all_permissions(self, user_obj, obj=None):
    """Return a set of permission strings the user has."""
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
```

**Key Points:**
- Returns permissions as strings in format `"app_label.codename"`
- Caches all permissions in `_perm_cache` for performance
- Combines user-level, Django Group, and TenantGroup permissions

#### Method: `has_perm(user_obj, perm, obj=None)`

Main permission check method:

```python
def has_perm(self, user_obj, perm, obj=None):
    """Check if user has a specific permission."""
    if not user_obj.is_active:
        return False

    return perm in self.get_all_permissions(user_obj, obj)
```

**Key Points:**
- Simple check: is permission in the combined permission set?
- Leverages caching from `get_all_permissions()`
- Very fast after first call due to in-memory cache

### Performance Characteristics

#### Cache Hierarchy

The backend uses three levels of caching:

| Cache Name | Scope | Lifetime |
|------------|-------|----------|
| `_tenant_group_perm_cache` | TenantGroup permissions only | Per request |
| `_group_perm_cache` | Django Group + TenantGroup | Per request |
| `_perm_cache` | All permissions (user + groups) | Per request |

**Cache Invalidation:** Django automatically clears these caches when:
- User object is reloaded
- New request begins
- Permissions are modified

#### Performance Benchmarks

```python
# First permission check (database query)
user.has_perm('documents.add_document')  # ~5-8ms

# Subsequent checks (cache hit)
user.has_perm('documents.change_document')  # <1ms
user.has_perm('documents.delete_document')  # <1ms
user.has_perm('documents.view_document')    # <1ms
```

**Optimization:**
- Uses `select_related('content_type')` to avoid N+1 queries
- Single query retrieves all TenantGroup permissions per user
- Permissions formatted as strings once and cached

### API Serializer Integration

**File:** `src/paperless/serialisers.py`

The `ProfileSerializer` exposes inherited permissions to frontend clients:

```python
class ProfileSerializer(PasswordValidationMixin, serializers.ModelSerializer):
    inherited_permissions = serializers.SerializerMethodField()

    def get_inherited_permissions(self, obj) -> list[str]:
        """
        Get all inherited permissions from tenant groups.

        This includes permissions from:
        - TenantGroup (tenant-scoped groups)
        - Standard Django auth.Group (for backward compatibility)
        """
        permissions = set()

        # Get permissions from Django auth.Group
        permissions.update(obj.get_group_permissions())

        # Get permissions from TenantGroup
        if hasattr(obj, 'tenant_groups'):
            for tenant_group in obj.tenant_groups.all():
                for perm in tenant_group.permissions.all():
                    full_perm = f"{perm.content_type.app_label}.{perm.codename}"
                    permissions.add(full_perm)

        return sorted(list(permissions))
```

**API Response Example:**

```json
{
  "id": 5,
  "username": "acme-admin",
  "email": "admin@acme.com",
  "user_permissions": [],
  "inherited_permissions": [
    "documents.add_document",
    "documents.change_document",
    "documents.delete_document",
    "documents.view_document",
    "documents.add_tag",
    "documents.change_tag",
    "auth.add_user",
    "auth.change_user"
  ]
}
```

**Key Points:**
- Frontend receives complete permission list via `/api/users/profile/`
- Permissions separated into `user_permissions` (direct) and `inherited_permissions` (from groups)
- UI can check permissions client-side for menu visibility and feature access

---

## Admin Permissions List

### Permission Scope

Tenant admins receive **60 permissions** covering all tenant-scoped operations:

| Permission Category | Count | Examples |
|-------------------|-------|----------|
| **Documents** | 20 | `documents.add_document`, `documents.change_document` |
| **Tags** | 4 | `documents.add_tag`, `documents.delete_tag` |
| **Correspondents** | 4 | `documents.add_correspondent`, `documents.view_correspondent` |
| **Document Types** | 4 | `documents.add_documenttype`, `documents.change_documenttype` |
| **Custom Fields** | 8 | `documents.add_customfield`, `documents.view_customfieldinstance` |
| **Users & Auth** | 8 | `auth.add_user`, `auth.change_user`, `auth.view_user` |
| **Storage & Tasks** | 8 | `documents.add_storagepath`, `documents.view_paperlesstask` |
| **Notes & Views** | 4 | `documents.add_note`, `documents.add_savedview` |

### Excluded Permissions

Tenant admins **do not** have permissions for:
- ❌ Django Admin interface (`/admin/`)
- ❌ Cross-tenant operations
- ❌ Superuser-only actions
- ❌ Database schema changes
- ❌ System configuration

---

## Security Considerations

### Password Security

Admin passwords are automatically generated with:
- **Length**: 16 characters
- **Charset**: Letters (upper/lower), digits, and special characters
- **Strength**: ~95 bits of entropy

```python
def generate_secure_password(length=16):
    """Generate cryptographically secure random password."""
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))
```

:::caution Security Debt
Generated admin passwords do **not** enforce an initial password change requirement. Admins can continue using the auto-generated password indefinitely.

**Severity:** Low
**Category:** A07:2021 - Identification and Authentication Failures
**Tracked:** See [Security Debt Tracker](./deferred-findings.md)

**Mitigation (TODO):**
- Add `password_change_required` flag to `UserProfile`
- Redirect to password change page on first login
- Force password expiration after 90 days
:::

### Permission Assignment Logging

All permission assignments are logged for audit purposes:

```python
logger.info(f"Assigned {len(admin_permissions)} permissions directly to {username}")
```

**Log Output:**
```
[2026-01-22 19:31:28,635] [INFO] [paperless.tenant_admin]
Assigned 60 permissions directly to testcorp-admin
```

:::info Security Debt
The code logs admin user creation events but does **not** log individual permission assignments with permission names.

**Severity:** Info
**Category:** A09:2021 - Security Logging and Monitoring Failures
**Tracked:** See [Security Debt Tracker](./deferred-findings.md)

**Enhancement (TODO):**
```python
logger.info(f"Assigned permissions to {username}: {[p.codename for p in admin_permissions]}")
```
:::

### Tenant Isolation

Admin users are isolated to their tenant through multiple layers:

1. **UserProfile.tenant_id**: Links user to specific tenant
2. **TenantMiddleware**: Sets tenant context for all requests
3. **PostgreSQL RLS**: Enforces data isolation at database level

```python
# Admins cannot access other tenants' data
acme_admin = User.objects.get(username='acme-admin')
acme_admin.profile.tenant_id  # = UUID for "acme" tenant

# Even with permissions, queries are filtered by tenant
Document.objects.all()  # Only returns acme's documents (via RLS)
```

For complete tenant isolation details, see [Multi-Tenant Isolation Architecture](./tenant-isolation.md).

---

## Verification and Testing

### Test 1: Permission Count

Verify admin user has correct number of direct permissions:

```python
from django.contrib.auth.models import User

admin = User.objects.get(username='acme-admin')
print(f"Direct permissions: {admin.user_permissions.count()}")
# Expected: 60
```

### Test 2: Django has_perm() Check

Verify Django's permission system recognizes admin permissions:

```python
from django.contrib.auth.models import User

admin = User.objects.get(username='testcorp-admin')

# Test document permissions
assert admin.has_perm('documents.add_document')
assert admin.has_perm('documents.change_document')
assert admin.has_perm('documents.delete_document')
assert admin.has_perm('documents.view_document')

# Test tag permissions
assert admin.has_perm('documents.add_tag')
assert admin.has_perm('documents.view_tag')

# Test user management permissions
assert admin.has_perm('auth.add_user')
assert admin.has_perm('auth.change_user')
assert admin.has_perm('auth.view_user')
```

### Test 3: Authentication

Verify admin can authenticate with generated password:

```python
from django.contrib.auth import authenticate

# Use password from creation logs
password = "9L|alXr+>B/Hcl7$"
admin = authenticate(username='testcorp-admin', password=password)

assert admin is not None
assert admin.username == 'testcorp-admin'
```

### Test 4: Web UI Access

Verify admin can perform operations in the web interface:

```bash
# 1. Login as tenant admin
# 2. Navigate to http://testcorp.local:8000/documents/
# 3. Try creating a new document
# 4. Try adding a tag
# 5. Try managing users

# Expected: All operations succeed
```

---

## Troubleshooting

### Issue: Admin User Has No Permissions

**Symptom:**
```python
admin = User.objects.get(username='acme-admin')
admin.user_permissions.count()  # Returns 0
admin.has_perm('documents.add_document')  # Returns False
```

**Cause:** Admin user has no group memberships or TenantGroupBackend is not configured.

**Solution:**

```bash
# Verify TenantGroupBackend is configured
python manage.py shell
```

```python
from django.conf import settings
print(settings.AUTHENTICATION_BACKENDS)
# Should include 'paperless.auth_backends.TenantGroupBackend'

# Check user's TenantGroup membership
from django.contrib.auth.models import User
from documents.models import TenantGroup

admin = User.objects.get(username='acme-admin')
tenant_groups = TenantGroup.objects.filter(users=admin)
print(f"TenantGroups: {[g.name for g in tenant_groups]}")

# If no groups found, add user to admin group
if not tenant_groups.exists():
    from documents.signals.tenant_handlers import create_tenant_admin_group
    from paperless.models import Tenant

    tenant = Tenant.objects.get(subdomain='acme')
    admin_group = create_tenant_admin_group(tenant.id)
    admin_group.users.add(admin)
    print(f"Added {admin.username} to {admin_group.name}")
```

### Issue: TenantGroup Exists But Permissions Don't Work

**Symptom:**
```python
from documents.models import TenantGroup

admin_group = TenantGroup.objects.get(name='Tenant Admins')
admin_group.permissions.count()  # Returns 60
admin_group.users.filter(username='acme-admin').exists()  # Returns True

# But user still can't perform actions
admin = User.objects.get(username='acme-admin')
admin.has_perm('documents.add_document')  # Returns False
```

**Root Cause:** `TenantGroupBackend` is not registered in `AUTHENTICATION_BACKENDS`.

**Solution:** Verify backend is configured in `settings.py`:

```python
# src/paperless/settings.py
AUTHENTICATION_BACKENDS = [
    'guardian.backends.ObjectPermissionBackend',
    'paperless.auth_backends.TenantGroupBackend',  # ✅ Must be present
    'django.contrib.auth.backends.ModelBackend',
]
```

**Restart Required:** After modifying `AUTHENTICATION_BACKENDS`, restart Django:

```bash
# If using Docker
docker-compose restart app-web

# If using development server
python src/manage.py runserver
```

### Issue: Password Not Logged

**Symptom:** Admin user created but password not visible in logs.

**Cause:** Log level set too high or logs not being captured.

**Solution:**

```bash
# Check Django settings
# settings.py should have:
LOGGING = {
    'loggers': {
        'paperless.tenant_admin': {
            'level': 'INFO',  # Must be INFO or lower
        }
    }
}

# Check container logs
docker-compose logs app-web | grep "password"
```

### Issue: Admin Can't Login to Web UI

**Symptom:** Correct credentials but login fails with "Tenant not found".

**Cause:** Accessing via IP address instead of subdomain.

**Solution:**

```bash
# ❌ Wrong (no subdomain)
http://localhost:8000/

# ✅ Correct (subdomain for tenant)
http://acme.local:8000/
http://testcorp.local:8000/

# For local testing, add to /etc/hosts:
echo "127.0.0.1 acme.local testcorp.local" | sudo tee -a /etc/hosts
```

---

## Migration from Old Implementation

### Evolution of Permission Handling

#### Phase 1: User-Level Permissions Only (Pre-2026)

**Old Code:**
```python
# ❌ Permissions assigned to TenantGroup only
# Django's ModelBackend couldn't check TenantGroup
admin_group = create_tenant_admin_group(tenant.id)
admin_group.users.add(admin_user)
# Result: has_perm() returns False
```

#### Phase 2: Dual Assignment (Interim Fix - January 2026)

**Interim Code:**
```python
# ⚠️ Hybrid approach - permissions assigned to both
admin_group = create_tenant_admin_group(tenant.id)
admin_group.users.add(admin_user)

# Also assign directly to user for compatibility
admin_user.user_permissions.set(get_admin_permissions())
# Result: has_perm() returns True, but redundant data
```

#### Phase 3: Custom Authentication Backend (Current - January 2026)

**Current Code:**
```python
# ✅ TenantGroupBackend registered in settings.py
# Permissions only need to be assigned to TenantGroup
admin_group = create_tenant_admin_group(tenant.id)
admin_group.users.add(admin_user)

# TenantGroupBackend automatically recognizes these permissions
# Result: has_perm() returns True, no duplicate data
```

**Key Improvement:** Permissions are managed at the group level, not duplicated per user.

### Verifying Backend Configuration

Check that the backend is properly configured:

```python
from django.conf import settings

# Verify TenantGroupBackend is registered
backends = settings.AUTHENTICATION_BACKENDS
print(backends)
# Expected:
# [
#     'guardian.backends.ObjectPermissionBackend',
#     'paperless.auth_backends.TenantGroupBackend',  # ✅
#     'django.contrib.auth.backends.ModelBackend',
# ]
```

### Testing Permission Resolution

Verify the backend correctly resolves TenantGroup permissions:

```python
from django.contrib.auth.models import User
from documents.models import TenantGroup

# Get admin user
admin = User.objects.get(username='acme-admin')

# Check TenantGroup membership
tenant_groups = TenantGroup.objects.filter(users=admin)
print(f"TenantGroups: {[g.name for g in tenant_groups]}")
# Expected: ['Tenant Admins']

# Check permissions via TenantGroup
for group in tenant_groups:
    print(f"Group '{group.name}' has {group.permissions.count()} permissions")
# Expected: Group 'Tenant Admins' has 60 permissions

# Verify Django recognizes these permissions
print(f"has_perm('documents.add_document'): {admin.has_perm('documents.add_document')}")
# Expected: True ✅

# Check which backend provided the permission
from paperless.auth_backends import TenantGroupBackend
backend = TenantGroupBackend()
all_perms = backend.get_all_permissions(admin)
print(f"Total permissions from TenantGroupBackend: {len(all_perms)}")
# Expected: 60
```

---

## Code Examples

### Creating Tenant Admin Programmatically

```python
from paperless.models import Tenant
from django.contrib.auth.models import User
from documents.models import TenantGroup
from documents.permissions import get_admin_permissions
from documents.models.base import set_current_tenant_id

# Create tenant
tenant = Tenant.objects.create(
    name="New Company",
    subdomain="newco",
    is_active=True
)

# Admin is automatically created by signal handler
# Retrieve the admin user
admin = User.objects.get(username='newco-admin')

# Verify permissions
print(f"Permissions: {admin.user_permissions.count()}")  # Should be 60
print(f"Can add docs: {admin.has_perm('documents.add_document')}")  # Should be True
```

### Checking Admin Permissions

```python
from django.contrib.auth.models import User

def check_admin_permissions(username):
    """Check if admin has correct permissions setup."""

    admin = User.objects.get(username=username)

    # Check direct permissions
    direct_count = admin.user_permissions.count()
    print(f"Direct permissions: {direct_count}")

    # Check group membership
    groups = admin.groups.all()  # Django groups (not TenantGroup)
    print(f"Django groups: {[g.name for g in groups]}")

    # Check TenantGroup membership
    from documents.models import TenantGroup
    tenant_groups = TenantGroup.objects.filter(users=admin)
    print(f"TenantGroups: {[g.name for g in tenant_groups]}")

    # Test key permissions
    perms_to_test = [
        'documents.add_document',
        'documents.change_document',
        'documents.delete_document',
        'auth.add_user',
    ]

    for perm in perms_to_test:
        has_it = admin.has_perm(perm)
        print(f"  {perm}: {'✅' if has_it else '❌'}")

    # Expected output:
    # Direct permissions: 60
    # Django groups: []
    # TenantGroups: ['Tenant Admins']
    # documents.add_document: ✅
    # documents.change_document: ✅
    # documents.delete_document: ✅
    # auth.add_user: ✅

check_admin_permissions('acme-admin')
```

### Bulk Permission Updates

```python
from documents.models import TenantGroup
from documents.permissions import get_admin_permissions

def update_all_tenant_admin_permissions():
    """Update permissions for all tenant admin groups."""

    admin_permissions = get_admin_permissions()

    # Update all TenantGroups named "Tenant Admins"
    for group in TenantGroup.objects.filter(name='Tenant Admins'):
        # Update group permissions
        group.permissions.set(admin_permissions)
        print(f"Updated group '{group.name}' (tenant_id={group.tenant_id}): {len(admin_permissions)} permissions")

        # Users automatically get these permissions via TenantGroupBackend
        # No need to update user.user_permissions separately

update_all_tenant_admin_permissions()
```

---

## Performance Considerations

### Permission Assignment Cost

Assigning 60 permissions to a TenantGroup is a single database operation:

```sql
-- Django executes:
INSERT INTO documents_tenantgroup_permissions (tenantgroup_id, permission_id)
VALUES (5, 1), (5, 2), ..., (5, 60)
ON CONFLICT DO NOTHING;

-- Query time: <10ms
```

**Impact:** Negligible performance overhead during tenant creation. Permissions are assigned once per group, not per user.

### Permission Checking Cost

Django caches permissions in memory per request:

```python
# First call: database query
admin.has_perm('documents.add_document')  # ~5ms

# Subsequent calls: in-memory cache
admin.has_perm('documents.change_document')  # <1ms
admin.has_perm('documents.delete_document')  # <1ms
```

**Best Practice:** Permission checks are very fast after the first call in a request.

---

## Related Documentation

- [Multi-Tenant Isolation Architecture](./tenant-isolation.md) - Overall tenant isolation strategy
- [User Tenant Isolation](./user-tenant-isolation.md) - User model tenant filtering
- [Group Tenant Isolation](./group-tenant-isolation.md) - TenantGroup implementation
- [Security Debt Tracker](./deferred-findings.md) - Known security issues and deferred findings

---

## Summary

**Key Points:**

1. ✅ **Automatic Admin Creation**: Tenant admins are automatically created when new tenants are provisioned
2. ✅ **Custom Authentication Backend**: `TenantGroupBackend` extends Django's permission system to recognize `TenantGroup` permissions
3. ✅ **Group-Level Permissions**: Permissions are assigned to `TenantGroup`, not duplicated per user
4. ✅ **Seamless Integration**: Works with Django's standard `has_perm()` checks and DRF permission classes
5. ✅ **Performance Optimized**: Multi-level caching with <1ms permission checks after first query
6. ✅ **Full Tenant Isolation**: Admins receive **60 permissions** for full tenant-scoped access
7. ⚠️ **Security Debt**: Admin passwords do not expire or require initial change (tracked in [Security Debt Tracker](./deferred-findings.md))

**Architecture:**

```
User → TenantGroup → Permissions
         ↓
    TenantGroupBackend checks permissions
         ↓
    user.has_perm() returns True
```

**For Production:**

- ✅ Verify `TenantGroupBackend` is registered in `AUTHENTICATION_BACKENDS`
- ✅ Monitor admin user creation in logs
- ⚠️ Rotate admin passwords periodically
- ⚠️ Implement password change requirement on first login (TODO)
- ✅ Audit admin permission assignments
- ✅ Use strong password policies

**Related Documentation:**

- [Group Tenant Isolation](./group-tenant-isolation.md) - TenantGroup model implementation
- [Multi-Tenant Isolation Architecture](./tenant-isolation.md) - Overall isolation strategy
- [Security Debt Tracker](./deferred-findings.md) - Known security issues

---

**Last Updated:** 2026-01-23
**Applies To:** Paless v2.0+ (January 2026 - TenantGroupBackend implementation)
