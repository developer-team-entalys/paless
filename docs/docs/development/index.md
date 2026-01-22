---
sidebar_position: 1
title: Development Documentation
description: Development guides for Paperless NGX contributors
---

# Development Documentation

Welcome to the Paperless NGX development guides. This section covers tools, processes, and configurations used during development.

## Available Guides

### [Local Development Environment](./local-development-setup.md)
Docker Compose setup for local development using dev-env.sh script.

- Quick start guide with Docker Compose
- Complete dev-env.sh command reference
- Fresh base image build enforcement (January 2026 improvements)
- Service architecture and volume management
- Development workflow and hot reload
- Troubleshooting and performance tuning
- Migration from old development setup

### [Development Container Setup](./devcontainer-setup.md)
Set up VSCode DevContainer for consistent, containerized development environment.

- DevContainer configuration overview
- Getting started with VSCode integration
- Pre-configured debugging and tasks
- Services (Redis, Gotenberg, Tika)
- Database options (SQLite, PostgreSQL)
- Running tests and managing dependencies
- Troubleshooting and performance tuning

### [Codecov Configuration](./codecov-configuration.md)
Manage code coverage tracking across backend and frontend components.

- Component-based coverage tracking (backend/frontend)
- Coverage flags for Python and Node.js versions
- Pull request coverage status checks
- Bundle size analysis for JavaScript
- Threshold configuration and best practices
- Troubleshooting coverage integration issues

### [Multi-Tenant Celery Tasks Guide](./celery-multi-tenant-tasks.md)
Implement and manage Celery background tasks in multi-tenant deployments.

- Tenant context restoration pattern and best practices
- When to add `tenant_id` parameter to tasks
- Wrapper task pattern for scheduled execution
- Creating new tasks step-by-step
- API endpoint documentation for `/api/tasks/run/`
- Per-tenant vs global task execution patterns
- Comprehensive troubleshooting guide

## Quick Navigation

### I want to...

**Set up local development with Docker Compose**
→ Read [Local Development Environment](./local-development-setup.md)

**Set up VSCode DevContainer development**
→ Read [Development Container Setup](./devcontainer-setup.md)

**Start backend services for development**
→ See [Debugging and Running Services](./devcontainer-setup.md#available-vscode-configurations) in DevContainer Setup

**Debug Python or TypeScript code**
→ Follow [Available VSCode Configurations](./devcontainer-setup.md#available-vscode-configurations) for debugging setup

**Run tests and check coverage**
→ See [Running Tests](./devcontainer-setup.md#running-tests) in DevContainer Setup

**Understand code coverage requirements**
→ Read [Codecov Configuration](./codecov-configuration.md)

**Check why a PR failed coverage checks**
→ See [Troubleshooting](./codecov-configuration.md#troubleshooting) in Codecov Configuration

**Add a new Python version to coverage**
→ Follow [Adding a New Python Version](./codecov-configuration.md#adding-a-new-python-version)

**Adjust coverage thresholds**
→ See [Adjusting Coverage Thresholds](./codecov-configuration.md#adjusting-coverage-thresholds)

**Implement background tasks for document processing**
→ Read [Multi-Tenant Celery Tasks Guide](./celery-multi-tenant-tasks.md)

**Understand how scheduled tasks work per-tenant**
→ See [Scheduled Tasks: Per-Tenant vs Global Execution](./celery-multi-tenant-tasks.md#scheduled-tasks-per-tenant-vs-global-execution)

**Troubleshoot task execution errors**
→ Check [Troubleshooting](./celery-multi-tenant-tasks.md#troubleshooting) in Celery Tasks Guide

**Fix Docker build issues or stale cached images**
→ See [Troubleshooting](./local-development-setup.md#troubleshooting) in Local Development Environment

**Understand recent Docker build improvements**
→ Read [Docker Build Improvements](./local-development-setup.md#docker-build-improvements-january-2026)

**Understand tenant admin user creation**
→ Read [Tenant Admin Permissions](../security/tenant-admin-permissions.md)

**Debug permission issues for tenant admins**
→ See [Troubleshooting](../security/tenant-admin-permissions.md#troubleshooting) in Tenant Admin Permissions

## Development Stack

Paperless NGX development uses:
- **Backend**: Python with Django and Celery
- **Frontend**: TypeScript with React and Angular
- **Database**: SQLite (development) or PostgreSQL (production-like)
- **Message Queue**: Redis
- **Development Tools**: VSCode, DevContainers, Docker Compose

## Testing

### Backend Tests

Run Python tests with coverage:

```bash
pytest --cov=src --cov-report=xml
```

Coverage requirements:
- New code: 100% target, 75% minimum
- Overall: 1% minimum change allowed

### Frontend Tests

Run TypeScript/React tests with coverage:

```bash
npm run test:coverage
```

Coverage requirements:
- New code: 100% target, 75% minimum
- Overall: 1% minimum change allowed
- Bundle size: Warn if over 1MB

## Code Review

Pull requests require:
- All tests passing on Python 3.10, 3.11, 3.12
- All tests passing on Node.js 24.x
- Coverage targets met for new code
- No bundle size increase over 50KB
- Maintainer approval

---

**Last Updated**: 2026-01-20

For additional development information, see the Contributing Guide in the repository root.
