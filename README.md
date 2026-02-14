# DayZ Server Manager

A Docker-based DayZ server management system with a **Web UI** and REST API for full lifecycle control.

Based on [official Bohemia Interactive documentation](https://community.bistudio.com/wiki/DayZ:Hosting_a_Linux_Server) and [Valve's SteamCMD guide](https://developer.valvesoftware.com/wiki/SteamCMD).

Also thanks for the ideas and some of the code at: https://ceregatti.org/git/daniel/dayzdockerserver.git

## Features

- **Web UI** - Easy-to-use dashboard for server management
- **Ubuntu 24.04 LTS** base image for stability and compatibility
- **SteamCMD** installed directly from Valve (auto-updates)
- **Robust supervisor** with crash recovery and exponential backoff
- **REST API** for all management operations
- **Orchestration-agnostic** - works with Docker Compose, Kubernetes, etc.

## Web UI

The built-in web interface provides:

- **Dashboard**: Server status, start/stop/restart controls, uptime, active mods
- **Mods**: Install, activate/deactivate, and remove workshop mods
- **Config**: Edit serverDZ.cfg directly with syntax hints
- **Settings**: Server installation, updates, auto-restart toggle, maintenance tools

Access the UI at `http://your-server:8081` and log in with your `API_TOKEN`.

![Dashboard Screenshot](docs/dashboard.png)

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Docker Compose                                   │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐         │
│  │   web    │    │   api    │    │  server  │    │   init   │         │
│  │  (8081)  │───▶│  (8080)  │◄───│          │    │(one-shot)│         │
│  │          │    │          │    │          │    │          │         │
│  │  Nginx   │    │ FastAPI  │    │Supervisor│    │Permission│         │
│  │  React   │    │ REST API │    │+DayZSrv  │    │  Volume  │         │
│  │  UI      │    │          │    │          │    │  Setup   │         │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘         │
│         │              │                │               │               │
│         └──────────────┴────────────────┴───────────────┘               │
│                      Shared Volumes                                     │
│      (serverfiles, profiles, mpmissions, mods, control, homedir)       │
└────────────────────────────────────────────────────────────────────────┘
```

### Containers

| Container | Purpose | User | Ports |
|-----------|---------|------|-------|
| `init` | One-shot: fix permissions, initialize volumes | root | none |
| `api` | REST API for all management operations | user (1000) | 8080 |
| `server` | DayZServer process with supervisor | user (1000) | game ports |
| `web` | React UI (Nginx) with API proxy | nginx | 8081 |

### Communication

The API and server containers communicate via:
- **Unix socket** (`/control/supervisor.sock`): Real-time supervisor control
- **state.json**: Supervisor writes current state (uptime, restarts, status)
- **mod_param**: Mod command line parameters for server startup

This design is orchestration-agnostic and works with Docker Compose, Kubernetes, or any container runtime.

## Quick Start

1. **Clone and configure:**
   ```bash
   git clone <repo>
   cd dayz-server
   cp .env.example .env
   # Edit .env with your settings
   ```

2. **Start the stack:**
   ```bash
   docker compose up -d
   ```

3. **Set up Steam credentials (for mods):**
   ```bash
   # First, log in interactively to cache credentials
   docker compose exec -it api steamcmd +login YOUR_USERNAME
   # Complete MFA if prompted
   
   # Then set the username via API
   curl -X POST http://localhost:8080/steam/login \
     -H "Authorization: Bearer your-secret-token" \
     -H "Content-Type: application/json" \
     -d '{"username": "YOUR_USERNAME"}'
   ```

4. **Install the server:**
   ```bash
   curl -X POST http://localhost:8080/server/install \
     -H "Authorization: Bearer your-secret-token"
   ```

5. **Start the server:**
   ```bash
   curl -X POST http://localhost:8080/server/start \
     -H "Authorization: Bearer your-secret-token"
   ```

## Configuration

### Environment Variables

Key configuration options in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `USER_ID` | 1000 | User ID for file permissions (match your host user) |
| `API_PORT` | 8080 | Internal API port |
| `WEB_PORT` | 8081 | Web UI port |
| `API_TOKEN` | - | **Required** - Authentication token for API and Web UI |
| `API_AUTH_DISABLED` | false | Disable authentication (NOT for production) |
| `SERVER_PORT` | 2302 | Game port (UDP) |
| `STEAM_QUERY_PORT` | 27016 | Steam query port (UDP) |
| `EXPERIMENTAL` | - | Set to `1` for experimental/unstable branch |
| `SERVER_PARAMS` | - | Custom startup parameters (overrides defaults) |
| `SERVER_MEMORY_LIMIT` | 8g | Docker memory limit for server container |
| `SERVER_CPU_LIMIT` | 4 | Docker CPU limit (cores) for server container |
| `SERVER_MEMORY_RESERVE` | 4g | Minimum reserved memory for server |

### Server Parameters

The system provides default server parameters with an override mechanism:

```bash
# View current parameters and their source (default/override/command_string)
curl http://localhost:8080/server/params

# Override specific parameters
curl -X POST http://localhost:8080/server/params \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "port": "2402",
    "adminlog": true,
    "freezecheck": true
  }'

# Or set complete command string
curl -X POST http://localhost:8080/server/params \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{"command_string": "-port=2402 -adminlog -freezecheck"}'

# Clear all overrides, revert to defaults
curl -X DELETE http://localhost:8080/server/params \
  -H "Authorization: Bearer your-token"
```

### App Channel Selection

Switch between stable and experimental DayZ builds:

```bash
# Check current channel
curl http://localhost:8080/server/channel

# Switch to experimental
curl -X POST http://localhost:8080/server/channel \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{"channel": "experimental"}'

# Switch back to stable
curl -X POST http://localhost:8080/server/channel \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{"channel": "stable"}'
```

## API Endpoints

### Health & Status
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/status` | Get complete server status (state, uptime, mods, version) |

### Server Control
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/server/start` | Start the server |
| POST | `/server/stop` | Stop the server |
| POST | `/server/restart` | Restart the server |
| GET | `/server/params` | Get server parameters with source info |
| POST | `/server/params` | Update server parameters (direct or individual) |
| DELETE | `/server/params` | Clear parameter overrides, revert to defaults |
| GET | `/server/channel` | Get current app channel (stable/experimental) |
| POST | `/server/channel` | Set app channel |
| POST | `/server/auto-restart/enable` | Enable crash recovery |
| POST | `/server/auto-restart/disable` | Disable crash recovery (maintenance mode) |
| POST | `/server/maintenance/enable` | Enter maintenance mode (blocks auto-start) |
| POST | `/server/maintenance/disable` | Exit maintenance mode |
| POST | `/server/install` | Install server files |
| POST | `/server/update` | Update server files |
| POST | `/server/uninstall` | Uninstall server (container-safe) |

### Mod Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/mods` | List installed mods (with active_only filter) |
| POST | `/mods/install/{id}` | Install a workshop mod |
| DELETE | `/mods/{id}` | Remove a mod |
| POST | `/mods/{id}/activate` | Activate a mod |
| POST | `/mods/{id}/deactivate` | Deactivate a mod |
| POST | `/mods/{id}/mode` | Set explicit server/client override |
| POST | `/mods/bulk` | Bulk install/activate mods |
| POST | `/mods/update-all` | Update all installed mods |

### Configuration
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/config` | Get server config (raw serverDZ.cfg with password masking) |
| PUT | `/config` | Update server config |
| GET | `/config/structured` | Get structured config as JSON |
| PUT | `/config/structured` | Apply structured config (validated) |
| GET | `/config/schema` | Get config field metadata (types, descriptions, sections) |

### Map Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/maps` | List available maps and installed templates |
| GET | `/maps/{workshop_id}` | Get specific map info |
| GET | `/maps/template/{template}` | Get map by mission template name |
| POST | `/maps/{workshop_id}/install` | Install map mission files from GitHub |
| DELETE | `/maps/{workshop_id}` | Uninstall map |

### Steam Credentials
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/steam/status` | Check credential status |
| POST | `/steam/login` | Set Steam username for cached sessions |
| POST | `/steam/test` | Test Steam login |
| POST | `/steam/cached-config` | Import config.vdf (JSON body) |
| POST | `/steam/cached-config/upload` | Import config.vdf (file upload) |
| POST | `/steam/cached-config/raw` | Import config.vdf (raw text body) |

### Admin Operations
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/admin/setup-mpmissions` | Copy pristine missions if needed |
| GET | `/admin/storage` | Get player/world storage info |
| DELETE | `/admin/storage` | Wipe player/world storage (query param for specific dir) |
| GET | `/admin/cleanup` | Get cleanup info (core dumps, crash dumps, logs, temp) |
| POST | `/admin/cleanup` | Clean server files (query params for granular control) |

### Logging
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/logs/files` | List available log files |
| GET | `/logs` | Tail log file (bytes_count query param, default 20KB) |
| GET | `/logs/stream` | Stream log via server-sent events (SSE) |

### VPP Admin Tools
*Only available when VPP mod is installed*

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/vpp/password` | Set VPPAdminTools password |
| POST | `/vpp/superadmins` | Set superadmin Steam64 IDs (replace/append modes) |

## Authentication

Set `API_TOKEN` in your `.env` file. Include it in requests:

```bash
curl -X POST http://localhost:8080/server/start \
  -H "Authorization: Bearer your-secret-token"
```

Disable auth for development with `API_AUTH_DISABLED=true`.

## Map Management

The system supports official DayZ maps (Chernarus, Livonia) and community maps (Namalsk, Takistan, etc.). Maps can be installed with their mission files automatically downloaded from GitHub repositories.

### Installing a Map

```bash
# List available maps
curl http://localhost:8080/maps \
  -H "Authorization: Bearer your-token"

# Install a map (e.g., Namalsk - workshop ID 2289456201)
curl -X POST http://localhost:8080/maps/2289456201/install \
  -H "Authorization: Bearer your-token"

# Check installed template
curl http://localhost:8080/maps/template/namalsk \
  -H "Authorization: Bearer your-token"
```

### Switching Maps

After installing a map, edit your server config to use the new template:

```bash
# Update structured config with new template
curl -X PUT http://localhost:8080/config/structured \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{"template": "namalsk"}'
```

## Admin Operations

### Storage Management

Wipe player data, world state, or specific storage directories without losing mods:

```bash
# Check storage info
curl http://localhost:8080/admin/storage \
  -H "Authorization: Bearer your-token"

# Wipe all player/world storage
curl -X DELETE http://localhost:8080/admin/storage \
  -H "Authorization: Bearer your-token"

# Wipe specific directory (e.g., only players)
curl -X DELETE "http://localhost:8080/admin/storage?dir=players" \
  -H "Authorization: Bearer your-token"
```

### Server Cleanup

Remove core dumps, crash dumps, old logs, and temporary files:

```bash
# Check what can be cleaned
curl http://localhost:8080/admin/cleanup \
  -H "Authorization: Bearer your-token"

# Clean all (core dumps, crash dumps, logs, temp files)
curl -X POST http://localhost:8080/admin/cleanup \
  -H "Authorization: Bearer your-token"

# Clean specific items only
curl -X POST "http://localhost:8080/admin/cleanup?core_dumps=true&log_files=true" \
  -H "Authorization: Bearer your-token"
```

### Mission Files Setup

Copy pristine mission files from upstream to active directory:

```bash
curl -X POST http://localhost:8080/admin/setup-mpmissions \
  -H "Authorization: Bearer your-token"
```

## Log Streaming

### Tail Logs

Get the last N bytes of a log file:

```bash
# Default: last 20KB
curl http://localhost:8080/logs?file=script.log \
  -H "Authorization: Bearer your-token"

# Get last 50KB
curl "http://localhost:8080/logs?file=script.log&bytes_count=51200" \
  -H "Authorization: Bearer your-token"
```

### Real-time Streaming

Stream logs via Server-Sent Events (SSE) for real-time monitoring:

```bash
# Stream script.log
curl -N http://localhost:8080/logs/stream?file=script.log \
  -H "Authorization: Bearer your-token"
```

The stream will continue sending new log lines as they're written.

## VPP Admin Tools Integration

If you have the VPP Admin Tools mod installed, you can configure it via the API:

### Set Admin Password

```bash
curl -X POST http://localhost:8080/vpp/password \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{"password": "your-admin-password"}'
```

### Configure Superadmins

```bash
# Replace all superadmins
curl -X POST http://localhost:8080/vpp/superadmins \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{"steam_ids": ["76561198012345678"], "mode": "replace"}'

# Append to existing superadmins
curl -X POST http://localhost:8080/vpp/superadmins \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{"steam_ids": ["76561198087654321"], "mode": "append"}'
```

## Server Lifecycle

The supervisor in the server container:

1. **Auto-starts** the server if the binary exists
2. **Auto-restarts** on crash (with exponential backoff)
3. **Disables auto-restart** after 5 crashes in 5 minutes
4. **Reports state** to `/control/state.json`

### Maintenance Mode

For updates or major changes, use maintenance mode to prevent auto-start:

```bash
# Method 1: Using maintenance mode (recommended)
curl -X POST http://localhost:8080/server/maintenance/enable \
  -H "Authorization: Bearer your-token"

# Stop server
curl -X POST http://localhost:8080/server/stop

# Run update
curl -X POST http://localhost:8080/server/update

# Exit maintenance and start
curl -X POST http://localhost:8080/server/maintenance/disable \
  -H "Authorization: Bearer your-token"
curl -X POST http://localhost:8080/server/start

# Method 2: Using auto-restart disable (legacy)
curl -X POST http://localhost:8080/server/auto-restart/disable
curl -X POST http://localhost:8080/server/stop
curl -X POST http://localhost:8080/server/update
curl -X POST http://localhost:8080/server/auto-restart/enable
curl -X POST http://localhost:8080/server/start
```

## Volume Structure

| Volume | Purpose |
|--------|---------|
| `homedir` | Steam credentials |
| `serverfiles` | DayZ server installation |
| `profiles` | Server config, BattlEye, VPP, logs |
| `mpmissions` | Active mission files |
| `mpmissions-upstream` | Pristine mission files (backup/restore) |
| `mods` | Workshop mods |
| `control` | IPC between API and server (supervisor socket, state) |

## Development

```bash
# Run with live reload
docker compose up --build

# View logs
docker compose logs -f api server

# Shell into containers
docker compose exec api bash
docker compose exec server bash
```

## License

MIT
