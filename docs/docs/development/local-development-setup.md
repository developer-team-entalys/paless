---
sidebar_position: 3
title: Local Development Environment
description: Docker Compose setup for local development using dev-env.sh script
keywords: [development, docker, docker compose, local setup, dev environment]
---

# Local Development Environment

This guide covers the local development environment setup using Docker Compose and the `dev-env.sh` helper script for Paless development.

## Overview

The local development environment provides a complete multi-tenant Paless deployment running in Docker containers on your local machine. This setup includes:

- **Application Services**: Web server, Celery workers, and scheduler
- **Infrastructure Services**: PostgreSQL database, Redis message broker, MinIO object storage
- **Multi-Tenant Support**: Full tenant isolation with subdomain-based routing
- **Development Tools**: Hot reload, debugging capabilities, and log access

## Prerequisites

- **Docker**: Version 20.10+ with Docker Compose v2
- **Docker Resources**: Minimum 8GB RAM, 20GB disk space
- **Git**: For repository access
- **Bash**: For running dev-env.sh script (Linux/macOS/WSL)

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/developer-team-entalys/paless.git
cd paless
```

### 2. Start Environment

```bash
./dev-env.sh up
```

This command:
1. Builds the base Docker image from scratch
2. Builds component images (web, worker, scheduler) using fresh base
3. Starts all services with docker-compose
4. Runs database migrations
5. Creates initial tenant and admin users

### 3. Access Application

Once started, access the application at:

```
http://localhost:30080
```

For multi-tenant testing, configure local DNS entries:

```bash
# Add to /etc/hosts (Linux/macOS) or C:\Windows\System32\drivers\etc\hosts (Windows)
127.0.0.1 acme.local testcorp.local
```

Then access tenants:
- `http://acme.local:30080`
- `http://testcorp.local:30080`

## dev-env.sh Command Reference

The `dev-env.sh` script provides convenient commands for managing your local development environment.

### Available Commands

#### `./dev-env.sh up`

**Description**: Build and start all services

**What it does**:
1. Validates environment file exists (`.env.dev`)
2. Builds base image from `Dockerfile.base` (no cache, always fresh)
3. Builds component images from fresh base using `--pull --no-cache` flags
4. Starts services with `--force-recreate` to ensure clean state
5. Runs database migrations automatically
6. Creates default tenant if not exists

**Flags**:
- Forces fresh pull of base image layers
- Disables Docker build cache for reproducible builds
- Force-recreates containers even if unchanged

:::tip Fresh Base Image Build
The `up` command now uses `--pull --no-cache` to ensure component images always use the latest base image, preventing stale cached layers from causing issues.
:::

**Example**:
```bash
./dev-env.sh up
```

**Output**:
```
[INFO] Building base image...
[INFO] Base image built successfully
[INFO] Building component images (forcing use of fresh base image)...
[INFO] Starting services (forcing recreation)...
[SUCCESS] Services started successfully
```

---

#### `./dev-env.sh down`

**Description**: Stop and remove all containers

**What it does**:
1. Stops all running containers
2. Removes containers and networks
3. Preserves volumes (data persists)

**Example**:
```bash
./dev-env.sh down
```

---

#### `./dev-env.sh restart [service]`

**Description**: Restart specific service or all services

**Arguments**:
- `[service]` (optional): Name of service to restart (e.g., `app-web`, `app-worker`)

**Example**:
```bash
# Restart all services
./dev-env.sh restart

# Restart only web server
./dev-env.sh restart app-web
```

---

#### `./dev-env.sh logs [service]`

**Description**: View logs from services

**Arguments**:
- `[service]` (optional): Name of service to view logs for

**Flags**:
- `-f` or `--follow`: Follow log output (live tail)

**Example**:
```bash
# View all logs
./dev-env.sh logs

# Follow web server logs
./dev-env.sh logs -f app-web

# View worker logs
./dev-env.sh logs app-worker
```

---

#### `./dev-env.sh shell [service]`

**Description**: Open bash shell in running container

**Arguments**:
- `[service]`: Service name (defaults to `app-web`)

**Example**:
```bash
# Shell into web container
./dev-env.sh shell

# Shell into worker container
./dev-env.sh shell app-worker
```

**Common use cases**:
```bash
# Inside container shell
python manage.py shell        # Django shell
python manage.py migrate       # Run migrations
python manage.py test          # Run tests
```

---

#### `./dev-env.sh rebuild`

**Description**: Rebuild images without cache and restart services

**What it does**:
1. Stops running containers
2. Rebuilds base image from scratch
3. Rebuilds component images with `--pull --no-cache` flags
4. Restarts services with fresh containers

**When to use**:
- After modifying Dockerfiles
- After changing Python/Node dependencies
- When containers behave unexpectedly
- To ensure completely fresh build

:::warning No Cache Build
The `rebuild` command forces complete rebuild without using Docker's build cache. This ensures all dependencies are fresh but takes longer than cached builds.
:::

**Example**:
```bash
./dev-env.sh rebuild
```

**Output**:
```
[INFO] Stopping services...
[INFO] Rebuilding base image...
[INFO] Rebuilding service images without cache (forcing use of fresh base image)...
[SUCCESS] Images rebuilt successfully
[INFO] Starting services...
```

---

#### `./dev-env.sh clean`

**Description**: Remove all containers, volumes, and images

**What it does**:
1. Stops and removes all containers
2. Removes all volumes (⚠️ **deletes all data**)
3. Removes all built images
4. Cleans up networks

**Example**:
```bash
./dev-env.sh clean
```

:::danger Data Loss Warning
This command **permanently deletes**:
- All database data
- Uploaded documents
- User accounts
- Redis cache
- All Docker volumes

Use with caution! Consider backing up data first.
:::

---

#### `./dev-env.sh status`

**Description**: Show status of all services

**What it does**:
- Lists running containers
- Shows health status
- Displays port mappings

**Example**:
```bash
./dev-env.sh status
```

**Output**:
```
NAME                STATUS              PORTS
paless-app-web     Up 5 minutes        0.0.0.0:30080->8000/tcp
paless-app-worker  Up 5 minutes
paless-postgres    Up 5 minutes        5432/tcp
paless-redis       Up 5 minutes        6379/tcp
paless-minio       Up 5 minutes        9000-9001/tcp
```

---

## Docker Build Improvements (January 2026)

### Fresh Base Image Enforcement

The `dev-env.sh` script has been enhanced to ensure component images always use the freshest base image:

**Changes Applied**:

1. **`up` command improvements**:
   ```bash
   # Before (could use stale cached layers)
   docker compose up --build -d

   # After (forces fresh base image)
   docker compose build --pull --no-cache
   docker compose up --force-recreate -d
   ```

2. **`rebuild` command improvements**:
   ```bash
   # Before
   docker compose build --no-cache

   # After (pulls latest base layers)
   docker compose build --pull --no-cache
   ```

**Benefits**:
- ✅ Eliminates stale cached base image layers
- ✅ Ensures component images always built on latest base
- ✅ Prevents "works on my machine" issues from cached layers
- ✅ More reproducible builds across different machines

**Impact**:
- ⏱️ Slightly longer build times (no cache reuse)
- 💾 May use more disk space (new layers downloaded)
- 🔄 More reliable environment consistency

### Why This Matters

**Problem**: Previously, running `./dev-env.sh up` could reuse cached Docker layers even after the base image was rebuilt, causing component images to run with outdated dependencies.

**Solution**: The `--pull` flag forces Docker to pull the latest version of the base image before building, and `--no-cache` ensures component images are built fresh from that base.

**Example Scenario**:
```bash
# Day 1: Build base with Python 3.11.5
./dev-env.sh up

# Day 2: Update Dockerfile.base to Python 3.11.6, rebuild base
docker build -f Dockerfile.base -t paless:latest .

# Day 3: Restart services (before fix - would still use 3.11.5 cached layers!)
./dev-env.sh up

# Day 3: Restart services (after fix - uses fresh 3.11.6 base)
./dev-env.sh up  # Now correctly pulls and uses updated base
```

## Environment Configuration

### Environment File (.env.dev)

The development environment uses `.env.dev` for configuration:

```bash
# Database Configuration
POSTGRES_DB=paperless
POSTGRES_USER=paperless
POSTGRES_PASSWORD=paperless
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Redis Configuration
REDIS_HOST=redis
REDIS_PORT=6379

# MinIO Configuration
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_ENDPOINT=minio:9000

# Application Configuration
DEBUG=true
ALLOWED_HOSTS=*
SECRET_KEY=dev-secret-key-change-in-production
```

### Custom Configuration

Create `.env.dev.local` to override settings without modifying tracked files:

```bash
# .env.dev.local (gitignored)
DEBUG=false
LOG_LEVEL=DEBUG
```

## Service Architecture

### Service Overview

| Service | Purpose | Ports |
|---------|---------|-------|
| **app-web** | Granian HTTP server (API + UI) | 30080→8000 |
| **app-worker** | Celery worker (document processing) | - |
| **app-scheduler** | Celery beat (scheduled tasks) | - |
| **postgres** | PostgreSQL database | 5432 |
| **redis** | Message broker and cache | 6379 |
| **minio** | S3-compatible object storage | 9000, 9001 |

### Volume Mounts

Development volumes for persistence:

```yaml
volumes:
  postgres_data:      # Database files
  redis_data:         # Redis persistence
  minio_data:         # Object storage
  app_media:          # Uploaded documents
  app_data:           # Application data
```

## Development Workflow

### Typical Development Cycle

1. **Start environment**:
   ```bash
   ./dev-env.sh up
   ```

2. **Make code changes** in your editor

3. **View logs** to verify changes:
   ```bash
   ./dev-env.sh logs -f app-web
   ```

4. **Restart service** if needed:
   ```bash
   ./dev-env.sh restart app-web
   ```

5. **Run tests** in container:
   ```bash
   ./dev-env.sh shell
   python manage.py test
   ```

6. **Stop environment** when done:
   ```bash
   ./dev-env.sh down
   ```

### Hot Reload

The development environment supports hot reload for:

- **Backend**: Django auto-reloads on Python file changes
- **Frontend**: Frontend dev server watches for TypeScript/React changes

No manual restart needed for most code changes!

## Troubleshooting

### Services Won't Start

**Symptom**: `./dev-env.sh up` fails or containers exit immediately

**Diagnostic Steps**:
```bash
# Check service status
./dev-env.sh status

# View error logs
./dev-env.sh logs

# Check Docker resources
docker system df
docker system info
```

**Common Causes**:
- Insufficient Docker memory (increase to 8GB+)
- Port conflicts (check if 30080, 5432, 6379 already in use)
- Corrupted volumes (try `./dev-env.sh clean` and restart)

---

### Database Migration Errors

**Symptom**: `migrate` command fails during startup

**Solution**:
```bash
# Shell into web container
./dev-env.sh shell

# Run migrations manually
python manage.py migrate

# Check migration status
python manage.py showmigrations
```

---

### Stale Cached Images

**Symptom**: Code changes not reflected after rebuild

**Solution**:
```bash
# Force complete rebuild without cache
./dev-env.sh rebuild

# Or manually rebuild base + components
docker build -f Dockerfile.base --no-cache -t paless:latest .
./dev-env.sh up
```

---

### Permission Issues

**Symptom**: Permission denied errors accessing volumes

**Solution**:
```bash
# Check volume permissions
docker volume inspect paless_app_data

# Reset volume permissions
./dev-env.sh shell
chown -R paperless:paperless /data /media
```

---

### Out of Disk Space

**Symptom**: Docker build fails with "no space left on device"

**Solution**:
```bash
# Remove unused images and volumes
docker system prune -a --volumes

# Check disk usage
docker system df
```

## Performance Tuning

### Docker Resource Allocation

Recommended Docker Desktop settings:

- **Memory**: 8GB minimum, 16GB recommended
- **CPUs**: 4+ cores for parallel processing
- **Disk**: 30GB+ for images and volumes
- **Swap**: 2GB+

### Build Optimization

**Faster Builds** (development):
```bash
# Skip base rebuild if unchanged
docker compose up --build -d
```

**Reliable Builds** (CI/production):
```bash
# Force fresh builds (current default)
./dev-env.sh rebuild
```

### Container Performance

Monitor resource usage:
```bash
# Real-time stats
docker stats

# Per-container resource usage
docker stats paless-app-web paless-app-worker
```

## Best Practices

### Do

✅ Use `./dev-env.sh up` for daily development
✅ Run `./dev-env.sh rebuild` after dependency changes
✅ Check logs with `./dev-env.sh logs -f` when debugging
✅ Use `./dev-env.sh shell` for Django management commands
✅ Keep `.env.dev` committed for team consistency
✅ Create `.env.dev.local` for personal overrides

### Don't

❌ Modify Docker Compose files directly (use environment variables)
❌ Run `./dev-env.sh clean` without backing up important data
❌ Commit `.env.dev.local` to version control
❌ Use development setup for production deployments
❌ Run multiple environments simultaneously (port conflicts)

## Migration from Old Setup

If migrating from an older development setup:

1. **Backup existing data**:
   ```bash
   docker exec paless-postgres pg_dump -U paperless paperless > backup.sql
   ```

2. **Stop old environment**:
   ```bash
   docker-compose down
   ```

3. **Clean old volumes** (optional):
   ```bash
   docker volume prune
   ```

4. **Start new environment**:
   ```bash
   ./dev-env.sh up
   ```

5. **Restore data** (optional):
   ```bash
   cat backup.sql | docker exec -i paless-postgres psql -U paperless paperless
   ```

## Related Documentation

- [Development Container Setup](./devcontainer-setup.md) - VSCode DevContainer alternative
- [Docker Image Architecture](../deployment/docker-images.md) - Production Docker images
- [Multi-Tenant Architecture](../deployment/multi-tenant-architecture.md) - Tenant isolation design

---

## Summary

The local development environment provides:

✅ **Complete Stack**: All services running locally in Docker
✅ **Fresh Builds**: Guaranteed fresh base image with `--pull --no-cache`
✅ **Developer Tools**: Convenient `dev-env.sh` commands
✅ **Hot Reload**: Automatic code reloading for rapid development
✅ **Multi-Tenant**: Full tenant isolation for testing
✅ **Reproducible**: Consistent environment across machines

**Key Commands**:
```bash
./dev-env.sh up        # Start environment
./dev-env.sh rebuild   # Force fresh rebuild
./dev-env.sh logs -f   # View live logs
./dev-env.sh shell     # Access container shell
./dev-env.sh down      # Stop environment
```

---

**Last Updated**: 2026-01-22
**Applies To**: Paless development environment with fresh base image enforcement
