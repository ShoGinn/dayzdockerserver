# DayZ Server Manager - Web UI

A React-based web interface for managing your DayZ server.

## Features

- **Dashboard**: Server status, start/stop/restart controls, uptime, active mods
- **Mods**: Install, activate/deactivate, and remove workshop mods
- **Config**: Edit serverDZ.cfg directly with syntax hints
- **Settings**: Server installation, updates, auto-restart toggle, maintenance tools

## Development

```bash
# Install dependencies
npm install

# Start dev server (proxies API to localhost:8080)
npm run dev

# Build for production
npm run build
```

## Authentication

The UI uses token-based authentication. Set `API_TOKEN` in your `.env` file, then enter the same token when logging into the web UI.

To disable authentication (not recommended for production):
```
API_AUTH_DISABLED=true
```

## Tech Stack

- React 18 + TypeScript
- Vite (build tool)
- React Router (navigation)
- Lucide React (icons)
- CSS Modules (styling)
