# Repository Guidance

This is the canonical instruction document for the repository. Keep it, the README, Compose,
and CI synchronized whenever architecture or verification changes.

## Architecture and platform

Docker Compose runs four services:

1. `init`: root-only, one-shot initialization of named-volume ownership and permissions.
2. `api`: unprivileged FastAPI management service.
3. `server`: unprivileged Python supervisor and the DayZ dedicated server process.
4. `web`: unprivileged nginx serving the React UI and proxying `/api` to `api`.

DayZ and SteamCMD require `linux/amd64`. Build `api` and `server` for that platform. Do not run
SteamCMD during an emulated image build or hide initialization failures. The `server` service
intentionally uses host networking because LAN discovery is a product requirement. Management
services remain on the Compose network; the direct API publish is localhost-bound by default.

The API and supervisor communicate through `/control/supervisor.sock`. The `control` volume is
owned by the configured `USER_ID:GROUP_ID`, its directory is `0770`, and the socket is `0660`.
The supervisor owns process state and writes `/control/state.json`. Do not replace socket IPC with
command files. Persistent volumes are `homedir`, `serverfiles`, `profiles`,
`mpmissions-upstream`, and `control`.

## Security invariants

- Authentication fails closed. With auth enabled, startup must reject a missing, empty, or example
  `API_TOKEN`. Only `/health` and CORS preflight are public. `/auth/verify`, `/status`, all reads,
  and all management endpoints require the shared Bearer-token verifier and constant-time compare.
- `API_AUTH_DISABLED=true` is an explicit local-development escape hatch only.
- CORS is disabled unless exact origins are configured in `CORS_ORIGINS`. Direct API access binds
  to `API_BIND_ADDRESS=127.0.0.1` by default.
- Treat all client-provided filenames and paths as hostile. Resolve them beneath the approved named
  volume root, reject absolute paths and traversal, and reject escaping symlinks and non-regular
  files. Log APIs may read only regular files under `/profiles`.
- The native log viewer requests bounded tails, never entire large logs. `bytes_count` is restricted
  to `1..524288` bytes (512 KiB), and backend reads must seek directly to that tail.
- Containers run unprivileged except the one-shot `init` service. Do not add sudo, privileged mode,
  broad capabilities, or writable bind mounts without explicit security review. Preserve
  `no-new-privileges`, capability drops, the web read-only filesystem, and required tmpfs mounts.
- A release may contain no vulnerability for which an ecosystem or vendor fix exists. Keep
  vendor-unfixed findings visible. Do not add vulnerability ignores without a reviewed rationale,
  owner, and expiry.

## Code and dependency policy

Python targets 3.12. `ty==0.0.65` is the only Python type checker. Ruff preview `ANN`, `PYI`, and
`PGH003` rules enforce annotation and suppression quality. Prefer precise types over `Any`; retain
`types-requests` for third-party stubs. Do not add a second Python type checker.

Pin reproducible build inputs, including container images by version and digest, package managers,
and GitHub Actions by commit SHA. Commit `uv.lock` and `web/pnpm-lock.yaml`; installs and CI use
frozen/locked modes. `pnpm-workspace.yaml` explicitly permits only reviewed install scripts.

Configure Dependabot with the `uv` ecosystem so Python updates include `uv.lock`. Group frontend
and GitHub Actions updates, stagger ecosystem schedules, and keep Node on an active LTS major until
the next even-numbered release enters LTS and receives explicit review.

Use centralized paths from `src/dayz/config/paths.py`. Workshop content is downloaded beneath
`/serverfiles/steamapps/workshop/content/221100`; installed and active mods use the established
symlink model. Preserve stable app ID `223350` and experimental app ID `1042420`.

Add a regression test for every security defect and behavioral change.

## Setup and verification

Run from the repository root unless a command changes directory:

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

cp .env.example .env
# Replace the example API_TOKEN before starting anything.
docker compose config --quiet
docker compose build
docker compose up -d init api web
curl --fail http://127.0.0.1:8080/health
curl --fail http://127.0.0.1:8081/
docker compose down

trivy fs --scanners vuln,misconfig,secret --ignore-unfixed \
  --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL --exit-code 1 .
trivy image --ignore-unfixed --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL \
  --exit-code 1 dayz-server:latest-api
trivy image --ignore-unfixed --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL \
  --exit-code 1 dayz-server:latest-server
trivy image --ignore-unfixed --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL \
  --exit-code 1 dayz-server:latest-web

# Vendor-unfixed findings remain visible and high/critical findings fail release checks.
trivy fs --scanners vuln,misconfig --severity HIGH,CRITICAL --exit-code 1 .
trivy image --severity HIGH,CRITICAL --exit-code 1 dayz-server:latest-api
trivy image --severity HIGH,CRITICAL --exit-code 1 dayz-server:latest-server
trivy image --severity HIGH,CRITICAL --exit-code 1 dayz-server:latest-web
```

On a native `linux/amd64` runner, also require:

```bash
docker run --rm --platform linux/amd64 --entrypoint steamcmd dayz-server:latest-server +quit
```
