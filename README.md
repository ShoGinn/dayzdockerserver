# DayZ Server Manager

A Docker Compose deployment for installing, configuring, and operating the Linux DayZ dedicated
server through a React web UI and authenticated FastAPI service.

## Architecture

| Service | Purpose | Runtime |
| --- | --- | --- |
| `init` | One-shot named-volume ownership and permission setup | root, capabilities restricted |
| `api` | Authenticated management API | unprivileged Python 3.12 on Ubuntu 24.04 |
| `server` | Supervisor and DayZ server process | unprivileged, `linux/amd64`, host network |
| `web` | React UI and `/api` reverse proxy | unprivileged nginx, read-only filesystem |

The API and supervisor share `/control/supervisor.sock` (`0660`) and state files on the `control`
volume (`0770`). The one-shot initializer assigns the configured `USER_ID:GROUP_ID` before either
management service starts. Existing named-volume data is retained across upgrades:

- `homedir`: Steam credentials and home data
- `serverfiles`: DayZ, workshop downloads, and active missions
- `profiles`: configuration, BattlEye, VPP, and logs
- `mpmissions-upstream`: pristine mission templates
- `control`: supervisor IPC and state

DayZ and SteamCMD require `linux/amd64`. The server intentionally retains host networking for LAN
discovery. The API and web services use normal Compose networking.

## Quick start

Requirements: Docker with Compose v2 and an amd64 Linux deployment host.

```bash
cp .env.example .env
openssl rand -hex 32
# Put that value in API_TOKEN in .env; the example token is rejected.
docker compose up -d
```

Open `http://localhost:8081` and log in with `API_TOKEN`. Direct API access is bound to
`127.0.0.1:8080` by default. Set `API_BIND_ADDRESS` only when direct remote API access is
deliberately required. Same-origin UI use needs no CORS; configure exact comma-separated origins in
`CORS_ORIGINS` for separate browser clients.

For authenticated API calls:

```bash
curl http://127.0.0.1:8080/auth/verify \
  -H 'Authorization: Bearer YOUR_TOKEN'
curl http://127.0.0.1:8080/status \
  -H 'Authorization: Bearer YOUR_TOKEN'
```

Only `GET /health` is public. `API_AUTH_DISABLED=true` is intended solely for explicit local
development.

## Steam and server setup

DayZ server app IDs are `223350` (stable) and `1042420` (experimental). Workshop content uses
client app ID `221100`.

```bash
docker compose exec -it api steamcmd +login YOUR_USERNAME

curl -X POST http://127.0.0.1:8080/steam/login \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"username":"YOUR_USERNAME"}'

curl -X POST http://127.0.0.1:8080/server/install \
  -H 'Authorization: Bearer YOUR_TOKEN'
curl -X POST http://127.0.0.1:8080/server/start \
  -H 'Authorization: Bearer YOUR_TOKEN'
```

Steam credentials persist in `homedir`; server and workshop content persist in `serverfiles`.
Installed mods remain symlinked from their workshop directories rather than copied.

## Log viewer

The web UI contains a native, selectable log viewer with line numbers, case-insensitive search and
match navigation, wrapping, follow-scroll, manual scroll-to-bottom, and two-second refreshes. It
loads bounded tails rather than complete logs.

Both `/logs` and `/logs/stream` accept only regular files confined below `/profiles`; absolute
paths, traversal, directories, and escaping symlinks return `400`. Tail sizes are restricted to
`1..524288` bytes:

```bash
curl 'http://127.0.0.1:8080/logs?filename=script.log&bytes_count=51200' \
  -H 'Authorization: Bearer YOUR_TOKEN'
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `USER_ID` | `1000` | Runtime and named-volume owner UID |
| `GROUP_ID` | `1000` | Runtime and named-volume owner GID |
| `API_TOKEN` | none | Required secret unless development bypass is explicit |
| `API_AUTH_DISABLED` | `false` | Explicit development-only auth bypass |
| `API_BIND_ADDRESS` | `127.0.0.1` | Host address for direct API publishing |
| `API_PORT` | `8080` | Direct API host port |
| `CORS_ORIGINS` | empty | Comma-separated exact browser origins |
| `WEB_PORT` | `8081` | Web UI host port |
| `SERVER_PORT` | `2302` | DayZ UDP server port |
| `STEAM_QUERY_PORT` | `27016` | Steam query UDP port |
| `EXPERIMENTAL` | empty | Set to `1` for the experimental app ID |

## Development and verification

Python targets 3.12 and uses exact `ty==0.0.65` as its only type checker. The frontend package
manager is pinned in `web/package.json`.

```bash
uv sync --locked
pnpm --dir web install --frozen-lockfile

uv run ruff check src tests
uv run ruff format --check src tests
uv run ty check src
uv run pytest -q

pnpm --dir web lint:check
pnpm --dir web test
pnpm --dir web build
pnpm --dir web audit --audit-level low

docker compose config --quiet
docker compose build
```

CI builds all runtime images for `linux/amd64`, verifies SteamCMD on a native amd64 runner, starts
the initializer/API/web smoke stack, runs secret and repository scans, and scans every image. The
release rule is zero vulnerabilities that have an available fix at every severity; vendor-unfixed
findings stay visible rather than being silently ignored.

See [AGENTS.md](AGENTS.md) for the complete security invariants and exact Trivy commands.

## License

MIT
