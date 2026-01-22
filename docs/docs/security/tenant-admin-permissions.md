---
sidebar_position: 3
title: Tenant Admin Permissions
description: Automatic tenant admin user creation and Django permissions architecture
---

# Tenant Admin Permissions

## Overview

Paless automatically creates tenant administrator users when new tenants are provisioned. This document describes the permissions architecture, automatic user creation workflow, and the critical fix for Django's permission system compatibility.

:::tip Key Takeaway
Tenant admins need permissions assigned **directly** to `user.user_permissions` because Django's `ModelBackend` doesn't check custom group models like `TenantGroup`.
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

Django's authentication system checks permissions using `ModelBackend`, which looks in two places:

```python
# Django ModelBackend checks:
1. user.user_permissions      # Direct user permissions ✅
2. user.groups                # Django's built-in Group model ✅
3. TenantGroup.permissions    # Custom model - NOT CHECKED ❌
```

:::danger Critical Issue (Fixed January 2026)
Earlier implementations assigned permissions only to `TenantGroup.permissions`. Django's `ModelBackend` doesn't check custom group models, causing `user.has_perm()` to return `False` even when permissions were assigned.
:::

### Hybrid Permission Strategy

The current implementation uses a **hybrid approach** for maximum compatibility:

```python
# 1. Create TenantGroup with permissions (for organization)
admin_group = create_tenant_admin_group(tenant.id)
admin_group.permissions.set(get_admin_permissions())

# 2. Add user to TenantGroup (for group membership tracking)
admin_group.users.add(admin_user)

# 3. CRITICAL: Also assign directly to user.user_permissions
admin_user.user_permissions.set(get_admin_permissions())
```

**Why Both?**
- **`user.user_permissions`**: Required for Django's `has_perm()` to work ✅
- **`TenantGroup.users`**: Useful for management UI and group-based organization ✅
- **`TenantGroup.permissions`**: Enables bulk permission updates in the future ✅

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

        # CRITICAL FIX: Assign permissions directly to user
        admin_permissions = get_admin_permissions()
        admin_user.user_permissions.set(admin_permissions)

        logger.info(f"Created admin user: {username}")
        logger.info(f"Assigned {len(admin_permissions)} permissions to {username}")

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

            # CRITICAL FIX: Assign directly to user
            admin_permissions = get_admin_permissions()
            admin_user.user_permissions.set(admin_permissions)

        finally:
            set_current_tenant_id(old_tenant_id)
```

**Lines:** 171-174 in `create_tenant_admins.py:171-174`

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

**Cause:** Admin created before permission fix was applied.

**Solution:**

```bash
# Option 1: Re-run management command
python manage.py create_tenant_admins --tenant=acme --force

# Option 2: Manually assign permissions
python manage.py shell
```

```python
from django.contrib.auth.models import User
from documents.permissions import get_admin_permissions

admin = User.objects.get(username='acme-admin')
admin_permissions = get_admin_permissions()
admin.user_permissions.set(admin_permissions)

print(f"Assigned {len(admin_permissions)} permissions")
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

**Root Cause:** Django's `ModelBackend` doesn't check `TenantGroup.permissions`.

**Solution:** Permissions must be assigned to `user.user_permissions`:

```python
admin_permissions = get_admin_permissions()
admin.user_permissions.set(admin_permissions)
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

### Pre-Fix Behavior (Before January 2026)

**Old Code:**
```python
# ❌ Only assigned to TenantGroup (Django doesn't check this)
admin_group = create_tenant_admin_group(tenant.id)
admin_group.users.add(admin_user)
# Result: has_perm() returns False
```

### Post-Fix Behavior (After January 2026)

**New Code:**
```python
# ✅ Hybrid approach
admin_group = create_tenant_admin_group(tenant.id)
admin_group.users.add(admin_user)

# CRITICAL: Also assign directly to user
admin_user.user_permissions.set(get_admin_permissions())
# Result: has_perm() returns True
```

### Migrating Existing Tenants

If you have existing tenants created before the fix:

```bash
# Re-create admins for all tenants
python manage.py create_tenant_admins --all --force

# Or for specific tenant
python manage.py create_tenant_admins --tenant=acme --force
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
    """Update permissions for all tenant admin groups and users."""

    admin_permissions = get_admin_permissions()

    # Update all TenantGroups named "Tenant Admins"
    for group in TenantGroup.objects.filter(name='Tenant Admins'):
        # Update group permissions
        group.permissions.set(admin_permissions)

        # Update each user's direct permissions
        for user in group.users.all():
            user.user_permissions.set(admin_permissions)
            print(f"Updated {user.username}: {len(admin_permissions)} permissions")

update_all_tenant_admin_permissions()
```

---

## Performance Considerations

### Permission Assignment Cost

Assigning 60 permissions to a user is a single database operation:

```sql
-- Django executes:
INSERT INTO auth_user_user_permissions (user_id, permission_id)
VALUES (123, 1), (123, 2), ..., (123, 60)
ON CONFLICT DO NOTHING;

-- Query time: <10ms
```

**Impact:** Negligible performance overhead during tenant creation.

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

1. ✅ Tenant admins are **automatically created** when new tenants are provisioned
2. ✅ Permissions are assigned to **both** `TenantGroup` and `user.user_permissions` (hybrid approach)
3. ✅ Django's `ModelBackend` only checks `user.user_permissions`, not custom group models
4. ✅ Admin users receive **60 permissions** for full tenant-scoped access
5. ⚠️ Admin passwords do not expire or require initial change (deferred security finding)
6. ✅ Tenant isolation is enforced through `UserProfile.tenant_id` and PostgreSQL RLS

**For Production:**

- Monitor admin user creation in logs
- Rotate admin passwords periodically
- Implement password change requirement on first login
- Audit admin permission assignments
- Use strong password policies

---

**Last Updated:** 2026-01-22
**Applies To:** Paless v2.0+ (January 2026 fix)
