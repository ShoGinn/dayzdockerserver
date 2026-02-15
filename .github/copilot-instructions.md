# Copilot Instructions for DayZ Docker Server

## Repository Overview

**Purpose:** Full-stack Docker application for managing DayZ dedicated servers, featuring server installation, updates, mod management, mission configuration, and real-time monitoring.

**Tech Stack:**

- **Backend:** Python 3.12+ (FastAPI, Pydantic, uvicorn)
- **Frontend:** React 19 + TypeScript (Vite, React Router, Lucide icons)
- **Build:** Docker multi-stage (4 stages), docker-compose orchestration
- **Architecture:** Unix socket IPC between API and server supervisor; strict type checking (mypy + Pydantic)
- **Code Quality:** Ruff (linting, 100 char line limit), Biome (frontend linting/formatting)

**Size:** ~2K files including 40+ mod directories and configuration templates. Key directories: `src/dayz/` (Python package), `web/src/` (React app), `files/` (config templates and mod symlinks).

---

## Build & Environment Setup

### Prerequisites

- **Python 3.12+** with `uv` package manager (https://docs.astral.sh/uv/) — **REQUIRED** for all Python operations
- **Node 18+ LTS** with `pnpm` package manager (https://pnpm.io/) — **REQUIRED** for frontend work
- **Docker 20.10+** with BuildKit enabled
- **Docker Compose 2.0+**

### Commands (All Tested)

**1. Bootstrap Environment**

```bash
# Install Python dependencies using uv (DO NOT use .venv manually)
cd /Users/scottginn/Coding/dayzdockerserver
uv sync  # Installs deps + dev tools into uv's managed environment

# Install frontend dependencies using pnpm
cd web && pnpm install && cd ..
```

**2. Lint Code**

```bash
# Backend Python linting (100 char line limit, strict rules) — run via uv
uv run ruff check src/

# Backend Python formatting (auto-fix) — run via uv
uv run ruff format src/

# Frontend TypeScript/CSS linting — use pnpm
cd web && pnpm lint:check && cd ..

# Frontend auto-formatting — use pnpm
cd web && pnpm lint && cd ..
```

**3. Type Checking**

```bash
# Backend (STRICT MODE - required for all new code) — run via uv
uv run mypy src/
# Error: disallow_untyped_defs = True, check_untyped_defs = True
# All functions must have explicit type annotations
```

**4. Build Docker Images**

```bash
# Full multi-stage build (2-3 min first time, ~30s with cache)
docker compose build

# Build specific service
docker compose build web   # Frontend only
docker compose build api   # API only
docker compose build server # Server supervisor only
```

**5. Run Application**

```bash
# Start all services (API on 8080, Web on 8081)
docker compose up -d

# View logs
docker compose logs -f api server web

# For frontend-only development (requires running API container) — use pnpm
cd web && pnpm dev  # HMR on http://localhost:3000, proxies /api to :8080

# For frontend with mock API (no backend needed) — use pnpm
cd web && VITE_API_MOCK=true pnpm dev
```

**6. Environment Configuration**

```bash
# Copy example to .env.local (required for docker compose)
cp .env.example .env.local

# Key variables:
# API_TOKEN=<generate-your-token>  # Required for auth (all endpoints except /health, /status)
# USER_ID=1000                      # Must match host UID for volume permissions
# SERVER_MEMORY_LIMIT=8g            # Docker memory limit for server container
```

---

## Project Layout & Architecture

### Backend Structure (`src/dayz/`)

- **config/models.py** (746 lines) → Pydantic models for server config, parameters, request/response validation
- **config/paths.py** (132 lines) → **SINGLE SOURCE OF TRUTH for all internal paths** (volumes, config files); never hardcode paths
- **core/server.py** (876 lines) → ServerControl/ServerManager: install, update, start, stop server
- **core/mods.py** (569 lines) → ModManager: workshop mod installation, activation, symlink management
- **core/maps.py** (368 lines) → MapManager: 10+ registered maps with install logic
- **core/steam.py** (472 lines) → SteamCMD wrapper: login, credentials, binary management
- **services/api.py** (872 lines) → FastAPI app entry point; routes for server, mods, maps, config, admin
- **services/supervisor.py** (698 lines) → DayZ process manager: auto-start, restart logic (exponential backoff), state file updates
- **utils/** → Helper functions: subprocess, privilege dropping, VDF parsing, version extraction, path utilities

### Frontend Structure (`web/src/`)

- **main.tsx** → React entry, Vite app root
- **App.tsx** → Router with protected routes (requires auth token)
- **api.ts** (311 lines) → Mock-aware HTTP client; all endpoints prefixed `/api/`
- **pages/** → Dashboard, Mods, Maps, Config, Logs, Settings, Login
- **components/** → Reusable: Layout, Card, Button, StatusBadge, Toast
- **hooks/** → useAuth (token storage), useServerStatus (polling), useMapInfo, useOperation (async state)

### Configuration Files

- **pyproject.toml** → Python dependencies (FastAPI, Pydantic, uvicorn, dev: mypy, pytest, ruff), tool configs
- **biome.json** → Frontend: single quotes, no semicolons, 100 char line width, 2-space indent
- **Dockerfile** → 4 stages: web-build (Node), base (Ubuntu 24.04 + SteamCMD deps), api (FastAPI), server (supervisor), web (Nginx)
- **docker-compose.yml** → 4 services (init, api, server, web) with health checks, volumes, resource limits
- **files/serverDZ.cfg.example** → Server config template
- **.env.example** → Required variables: API_TOKEN, USER_ID, port mappings, memory/CPU limits

### Docker Volumes (Persistent)

- **dayz-homedir** → Steam authentication credentials
- **dayz-serverfiles** → DayZ installation directory
- **dayz-profiles** → Active server config, BattlEye, logs
- **dayz-mpmissions-upstream** → Pristine mission templates (backup)
- **dayz-mpmissions** → Active missions (read by server)
- **dayz-mods** → Workshop mods (symlinked to active/inactive)
- **dayz-control** → IPC: supervisor.sock, state.json, mod parameters

---

## Validation & CI Checks

**What runs on every PR:**

1. **Python linting** → `ruff check src/` (must pass, 100 char line limit enforced)
2. **Python type checking** → `mypy src/` (STRICT MODE; disallow_untyped_defs required)
3. **Frontend linting** → `npm run lint:check` in web/ (Biome rules)
4. **Docker build** → `docker compose build` (validates Dockerfile, all stages complete)

**To validate locally before pushing:**

```bash
uv run ruff check src/ && uv run ruff format src/
uv run mypy src/
cd web && pnpm lint:check && pnpm build && cd ..
docker compose build
```

**Important:** No unit tests exist yet (pytest configured but no test files). Validation relies on strict type checking and linting. Add integration tests cautiously—existing code has no test patterns established.

---

## Critical Implementation Details & Gotchas

**1. Path Centralization (MUST DO)**

- All paths defined in `src/dayz/config/paths.py`
- Never hardcode `/profiles/`, `/mods/`, `/serverfiles/` etc. in code
- Always import: `from dayz.config.paths import Paths`; use `Paths.SERVER_CONFIG`, `Paths.MODS_DIR`, etc.

**2. Unix Socket IPC (Not File-Based)**

- API ↔ Supervisor communication via `/control/supervisor.sock` (socket, not command files)
- Supervisor is the source of truth for server state
- State written to `/control/state.json` (uptime_seconds, restart_count, state enum)
- Use `DayZSupervisorClient` from `services/supervisor.py` for socket ops

**3. Pydantic Strict Type Validation**

- All request models use Pydantic v2 with strict validation
- All dataclasses use `frozen=True` where applicable
- mypy strict mode: no `Any`, no implicit Optional—be explicit

**4. Non-Root User Privilege Handling**

- Containers run as user 1000 (not root)
- SteamCMD requires passwordless sudo (`/etc/sudoers.d/`)
- Helper: `should_drop_privileges()` in `utils/process_utils.py`
- Check before spawning subprocesses

**5. Mod Mode Symlinks**

- Mods are NOT copied; they're symlinked to `/mods/active/` or `/mods/inactive/`
- Mod server/client designation stored in `/control/mod_modes.json`
- Passed to DayZ via `-mod=` parameter at startup
- ModManager handles symlink lifecycle

**6. Mission File Architecture**

- `/mpmissions-upstream/` = pristine templates (backup for restore)
- `/mpmissions/` = active missions (server reads these at runtime)
- Design: copy upstream → active when installing/updating map

**7. Channel Switching (Steam App IDs)**

- Stable build: Steam App ID 223350
- Experimental: Steam App ID 1042420
- Channel override: create `/control/app_channel` file
- Always sync to correct App ID when switching

**8. State File Format (`/control/state.json`)**

- JSON structure: `{ "state": "running"|"stopped"|"crashed", "uptime_seconds": int, "restart_count": int }`
- Written by supervisor loop every iteration
- API reads this for status endpoint
- Freshness checked by health checks; lag > 60s = unhealthy

**9. Token Authentication**

- All endpoints except `/health`, `/status`, `/login` require Bearer token
- Header: `Authorization: Bearer {API_TOKEN}`
- Token validation: `depends(get_current_user)` in API routes
- Frontend stores token in `localStorage` (useAuth hook)

**10. No Tests Yet—Use Type Checking**

- Pytest configured but zero test files exist
- Agent should NOT assume tests will catch errors
- Rely on mypy + Pydantic validation + manual testing
- If adding tests, establish pattern first (no existing test structure to follow)

**11. Frontend Mock API**

- Set `VITE_API_MOCK=true` environment variable when running `pnpm dev` to run frontend without backend
- Useful for UI-only development and prototyping
- Mock responses in `/web/src/mocks/`

**12. Docker Resource Limits**

- API: 2GB mem, 2 CPU (~512MB reserve)
- Server: 8GB mem (configurable), 4 CPU (configurable via env vars)
- Web: 256MB mem, 0.5 CPU (~64MB reserve)
- Adjust via `SERVER_MEMORY_LIMIT`, `SERVER_CPU_LIMIT` in `.env.local`

**13. Health Checks**

- API health: runs every 30s, checks `/health` endpoint (5s timeout, fails after 3 retries, 10s startup grace)
- Server health: runs every 30s, executes `dayz.cli.healthcheck` PID check (10s timeout, fails after 5 retries, 60s startup grace)
- Check container logs if health check fails

**14. 32-bit Library Dependency**

- SteamCMD requires 32-bit glibc (`lib32gcc-s1`, `lib32stdc++6`)
- Ubuntu 24.04 base image includes these
- Do not remove if updating dependencies

**15. Nginx Proxy Timeouts**

- Web container proxies `/api/` to API container with 300s read/send timeouts
- Accommodates long-running operations (install, update)
- Do not reduce without testing

---

## Trust This Documentation

Coding agents should trust this documentation first and search only if:

1. Information here is outdated or contradicts observed reality
2. A specific implementation detail is missing for a particular component
3. A new feature requires understanding not covered here

When in doubt about paths, command sequences, or architecture, refer to the specific files listed rather than inferring from directory structure.
