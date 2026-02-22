# CLAUDE.md

Full-stack Docker application for managing DayZ dedicated servers. Python/FastAPI backend, React/TypeScript frontend, 3-container Docker architecture with Unix socket IPC.

## Verification & Validation

Run these after making changes. No unit tests exist — validation relies on strict linting and type checking.

```bash
# Python
uv run ruff check src/
uv run ruff format --check src/
uv run mypy src/

# Frontend (from repo root)
cd web && pnpm lint:check && cd ..
cd web && pnpm build && cd ..     # runs tsc + vite build

# Docker
docker compose build
```

## Development Setup

```bash
uv sync                           # Python deps (requires uv)
cd web && pnpm install && cd ..   # Frontend deps (requires pnpm)
cp .env.example .env              # Required for docker compose
```

## Running the App

```bash
docker compose up -d                     # All services (API :8080, Web :8081)
cd web && pnpm dev                       # Frontend dev server (:3000, proxies /api to :8080)
cd web && VITE_API_MOCK=true pnpm dev    # Frontend with mock API (no backend needed)
```

## Architecture

**3 containers:** api (FastAPI) → server (DayZ supervisor) → web (Nginx + React)

**IPC:** API ↔ Supervisor communicate via Unix socket at `/control/supervisor.sock`. Supervisor writes state to `/control/state.json`. Use `DayZSupervisorClient` from `services/supervisor.py`.

**5 named volumes:** homedir (Steam creds), serverfiles (DayZ install + workshop mods + active missions), profiles (config/BattlEye + active mod symlinks), mpmissions-upstream (pristine mission templates), control (socket + state + mod params)

**Key source paths:**
- `src/dayz/config/paths.py` — Single source of truth for all internal paths
- `src/dayz/config/models.py` — Pydantic models for config and validation
- `src/dayz/services/api.py` — FastAPI routes
- `src/dayz/services/supervisor.py` — DayZ process manager + socket client
- `src/dayz/core/` — server.py, mods.py, maps.py, steam.py
- `web/src/` — React app (pages/, components/, hooks/, api.ts)

## Critical Rules

1. **Never hardcode paths.** Import from `dayz.config.paths.Paths` — always.
2. **Socket IPC, not files.** API talks to supervisor via Unix socket, not command files.
3. **Strict types everywhere.** mypy strict mode: no `Any`, no implicit Optional, all functions annotated.
4. **Non-root containers.** Run as UID 1000. SteamCMD uses passwordless sudo. Check `should_drop_privileges()` before spawning subprocesses.
5. **Mods are symlinked, not copied.** SteamCMD downloads to `/serverfiles/steamapps/workshop/`. Install creates `/serverfiles/@ModName` symlink. Activate creates `/profiles/@ModName` symlink. Deactivate removes the `/profiles/` symlink. Mod modes stored in `/control/mod_modes.json`.
6. **Mission files: upstream vs active.** `/mpmissions-upstream/` = pristine backups. `/serverfiles/mpmissions/` = what the server reads. Copy upstream → active on install/update.
8. **Core dumps disabled.** The server container sets `ulimits: core: 0` to prevent multi-GB dump files from DayZ crashes filling `/serverfiles`.
7. **Auth required.** All API endpoints except `/health`, `/status`, `/login` need `Authorization: Bearer {API_TOKEN}`.

## Code Style

**Python:** Ruff formatter — double quotes, 100 char lines, space indent. Ruff linter with bugbear, simplify, pyupgrade rules.

**Frontend:** Biome — single quotes, semicolons as needed, 100 char lines, 2-space indent, trailing commas (ES5).

See `.github/copilot-instructions.md` for exhaustive architectural details.
