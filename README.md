# DayZ Server Manager

A Docker-based DayZ server management system with a **Web UI** and REST API for full lifecycle control.

Based on [official Bohemia Interactive documentation](https://community.bistudio.com/wiki/DayZ:Hosting_a_Linux_Server) and [Valve's SteamCMD guide](https://developer.valvesoftware.com/wiki/SteamCMD).

Also thanks for the ideas and some of the code at: https://ceregatti.org/git/daniel/dayzdockerserver.git

## Features

- **Web UI** - Easy-to-use dashboard for server management
- **Ubuntu 22.04 LTS** base image for stability and compatibility
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

Access the UI at `http://your-server:8080` and log in with your `API_TOKEN`.

![Dashboard Screenshot](docs/dashboard.png)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Docker Compose                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   api        │    │   server     │    │   init       │       │
│  │   (8080)     │◄───│              │    │   (one-shot) │       │
│  │              │    │              │    │              │       │
│  │ FastAPI      │    │ Supervisor   │    │ Permissions  │       │
│  │ Web UI       │    │ + DayZServer │    │ Volume setup │       │
│  │ REST API     │    │              │    │              │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                   │                   │                │
│         └───────────────────┴───────────────────┘                │
│                    Shared Volumes                                │
│         (serverfiles, profiles, mpmissions, mods, control)      │
└─────────────────────────────────────────────────────────────────┘
```

### Containers

| Container | Purpose | User | Ports |
|-----------|---------|------|-------|
| `init` | One-shot: fix permissions, initialize volumes | root | none |
| `api` | Web UI + REST API for all management operations | root | 8080 |
| `server` | DayZServer process with supervisor | user (1000) | game ports |

### Communication

The API and server containers communicate via the `/control` shared volume:
- **command**: API writes commands (start, stop, restart)
- **state.json**: Supervisor writes current state
- **mod_param**: Mod command line parameters

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
     -H "Content-Type: application/json" \
     -d '{"username": "YOUR_USERNAME"}'
   ```

4. **Install the server:**
   ```bash
   curl -X POST http://localhost:8080/server/install
   ```

5. **Start the server:**
   ```bash
   curl -X POST http://localhost:8080/server/start
   ```

## API Endpoints

### Server Control
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/status` | Get complete server status |
| POST | `/server/start` | Start the server |
| POST | `/server/stop` | Stop the server |
| POST | `/server/restart` | Restart the server |
| POST | `/server/install` | Install server files |
| POST | `/server/update` | Update server files |

### Mod Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/mods` | List installed mods |
| POST | `/mods/install/{id}` | Install a mod |
| DELETE | `/mods/{id}` | Remove a mod |
| POST | `/mods/{id}/activate` | Activate a mod |
| POST | `/mods/{id}/deactivate` | Deactivate a mod |
| POST | `/mods/bulk` | Bulk install/activate mods |

### Configuration
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/config` | Get server config |
| PUT | `/config` | Update server config |
| GET | `/config/structured` | Get structured config |
| PUT | `/config/structured` | Apply structured config |

### Steam
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/steam/status` | Check credential status |
| POST | `/steam/login` | Set Steam username |
| POST | `/steam/test` | Test Steam login |

## Authentication

Set `API_TOKEN` in your `.env` file. Include it in requests:

```bash
curl -X POST http://localhost:8080/server/start \
  -H "Authorization: Bearer your-secret-token"
```

Disable auth for development with `API_AUTH_DISABLED=true`.

## Server Lifecycle

The supervisor in the server container:

1. **Auto-starts** the server if the binary exists
2. **Auto-restarts** on crash (with exponential backoff)
3. **Disables auto-restart** after 5 crashes in 5 minutes
4. **Reports state** to `/control/state.json`

### Maintenance Mode

For updates, disable auto-restart first:

```bash
# Disable auto-restart
curl -X POST http://localhost:8080/server/auto-restart/disable

# Stop server
curl -X POST http://localhost:8080/server/stop

# Run update
curl -X POST http://localhost:8080/server/update

# Re-enable and start
curl -X POST http://localhost:8080/server/auto-restart/enable
curl -X POST http://localhost:8080/server/start
```

## Volume Structure

| Volume | Purpose |
|--------|---------|
| `homedir` | Steam credentials |
| `serverfiles` | DayZ server installation |
| `profiles` | Server config, battleye, logs |
| `mpmissions` | Mission files |
| `mpmissions-upstream` | Pristine mission files |
| `mods` | Workshop mods |
| `control` | IPC between API and server |

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
