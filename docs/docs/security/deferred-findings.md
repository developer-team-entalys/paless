---
sidebar_position: 99
title: Security Debt Tracker
description: Deferred security findings to address before production
---

# Security Debt Tracker

This document tracks security findings that were deferred during development.
These issues should be addressed before moving to production.

:::caution Security Debt
The findings below represent known security issues that have been accepted
for the current development stage but **must be resolved before production**.
:::

## Summary

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High     | 0 |
| Medium   | 0 |
| Low      | 1 |
| Info     | 2 |

---

## Deferred Findings by Task

### Task: 93b69161...

**Date**: 2026-01-22
**Stage**: dev
**Description**: Fix tenant admin permissions - Django doesn't check TenantGroup, must assign to user.user_permissions

:::info Complete Documentation
For full details on the tenant admin permissions implementation, architecture, and usage, see [Tenant Admin Permissions](./tenant-admin-permissions.md).
:::

| Severity | Category | Description | Location |
|----------|----------|-------------|----------|
| LOW | A07:2021 - Identification and Authentication Failures | Generated admin passwords do not enforce an initial password change requirement. | `src/documents/signals/tenant_handlers.py:170-176, src/documents/management/commands/create_tenant_admins.py:148-154` |
| INFO | A09:2021 - Security Logging and Monitoring Failures | The code logs admin user creation events but does not log permission assignment  | `src/documents/signals/tenant_handlers.py:86-88` |
| INFO | Security Architecture | The fix duplicates permissions between TenantGroup and user.user_permissions due | `src/documents/signals/tenant_handlers.py:197-201, src/documents/management/commands/create_tenant_admins.py:171-174` |

**Resolution Notes:**
- Hybrid approach maintains both `TenantGroup` (for organization) and `user.user_permissions` (for Django compatibility)
- Django's `ModelBackend` only checks `user.user_permissions`, not custom group models
- All tenant admins now have 60+ permissions assigned directly for full functionality

