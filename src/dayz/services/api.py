#!/usr/bin/env python3
"""
DayZ Server Management API

Unified API for all server management operations:
- Server control (start/stop/restart)
- Server installation and updates
- Mod management
- Configuration management
- Steam credentials
- VPP Admin settings
"""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from dayz.config.models import (
    ConfigContent,
    HealthResponse,
    OperationResponse,
    ServerChannelRequest,
    ServerConfig,
    ServerParamsRequest,
    ServerParamsResponse,
    ServerStatusResponse,
    SteamCachedConfigRequest,
    SteamLoginRequest,
)
from dayz.config.paths import PROFILES_DIR
from dayz.core.maps import MapManager
from dayz.core.mods import ModManager
from dayz.core.server import ServerControl, ServerManager
from dayz.core.steam import CredentialsStatus, ImportResult, LoginTestResult, SteamCredentials
from dayz.mods import router as mods_router
from dayz.mods import vpp_api

# =============================================================================
# Configuration
# =============================================================================

API_TOKEN = os.getenv("API_TOKEN", "")
API_AUTH_DISABLED = os.getenv("API_AUTH_DISABLED", "").lower() in ("1", "true", "yes")

security = HTTPBearer(auto_error=False)


# =============================================================================
# Lifespan
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown"""
    # Startup
    logging.info("DayZ API starting...")

    # Initialize managers
    app.state.server = ServerManager()
    app.state.mods = ModManager()

    # VPP routes are gated via dependency; router included globally

    yield

    # Shutdown
    logging.info("DayZ API shutting down...")


# =============================================================================
# Application
# =============================================================================

app = FastAPI(
    title="DayZ Server API",
    description="Unified API for DayZ server management",
    version="2.0.0",
    lifespan=lifespan,
)

# FastAPI parameter sentinels (avoid function calls in defaults per linter)
FILE_REQUIRED = File(...)

# CORS for web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Authentication
# =============================================================================


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
) -> bool:
    """Verify bearer token if authentication is enabled"""
    if API_AUTH_DISABLED:
        return True
    if not API_TOKEN:
        return True
    if not credentials or credentials.credentials != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return True


# Attach modular VPP API router and OpenAPI filter
router_vpp = vpp_api.build_router(verify_token)
app.include_router(router_vpp)
vpp_api.attach_openapi_filter(app)


def get_server() -> ServerManager:
    """Get server manager from app state"""
    return cast(ServerManager, app.state.server)


def get_mods() -> ModManager:
    """Get mod manager from app state"""
    return cast(ModManager, app.state.mods)


# Attach mods router
router_mods = mods_router.create_router(get_mods, verify_token)
app.include_router(router_mods)


# =============================================================================
# Health & Status
# =============================================================================


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Health check endpoint"""
    control = ServerControl()
    state = control.get_state()
    return HealthResponse(
        status="ok",
        server_state=state.state,
        message=state.message,
    )


@app.get("/status", response_model=ServerStatusResponse, tags=["Server"])
async def get_server_status(server: ServerManager = Depends(get_server)) -> ServerStatusResponse:  # noqa: B008
    """Get complete server status"""
    status = server.get_status()
    return ServerStatusResponse(**status)


# =============================================================================
# Server Control
# =============================================================================


@app.post("/server/start", response_model=OperationResponse, tags=["Server"])
async def start_server(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Start the DayZ server"""
    success, message = server.start()
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return OperationResponse(success=True, message=message)


@app.post("/server/stop", response_model=OperationResponse, tags=["Server"])
async def stop_server(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Stop the DayZ server"""
    success, message = server.stop()
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return OperationResponse(success=True, message=message)


@app.post("/server/restart", response_model=OperationResponse, tags=["Server"])
async def restart_server(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Restart the DayZ server"""
    success, message = server.restart()
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return OperationResponse(success=True, message=message)


@app.get("/server/params", response_model=ServerParamsResponse, tags=["Server"])
async def get_server_params(
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> ServerParamsResponse:
    """Get current server parameters with source information.

    Returns structured parameter data including:
    - Individual parameter values
    - Full command string
    - Parameter source (default, override, or configured)
    """
    result = server.get_server_params_dict()
    return ServerParamsResponse(**result, success=True)


@app.post("/server/params", response_model=OperationResponse, tags=["Server"])
async def set_server_params(
    payload: ServerParamsRequest,
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Update server parameters.

    Two modes of operation:
    1. Direct command string (takes precedence):
       POST {"command_string": "-config=... -port=2302 ..."}

    2. Individual parameter updates (merged with current):
       POST {"port": 2302, "logs": true, "admin_log": true}

    Args:
        payload: Parameter update request

    Returns:
        Operation result with updated parameter details

    Raises:
        HTTPException: If update fails
    """
    success, message, updated_params = server.update_server_params(
        command_string=payload.command_string,
        port=payload.port,
        logs=payload.logs,
        admin_log=payload.admin_log,
        net_log=payload.net_log,
        extra_params=payload.extra_params,
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return OperationResponse(
        success=True,
        message=message,
        details={
            "command_string": updated_params.to_command_string(),
            "params": updated_params.model_dump(),
        },
    )


@app.delete("/server/params", response_model=OperationResponse, tags=["Server"])
async def clear_server_params(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Clear server params override, reverting to default parameters.

    Removes any custom parameter configuration and restores defaults.

    Returns:
        Operation result

    Raises:
        HTTPException: If clearing fails
    """
    success, message = server.clear_server_params_override()

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return OperationResponse(success=True, message=message)


@app.get("/server/channel", tags=["Server"])
async def get_server_channel(server: ServerManager = Depends(get_server)) -> dict:  # noqa: B008
    """Get current app channel"""
    channel = server.get_channel()
    return {"success": True, "channel": channel}


@app.post("/server/channel", response_model=OperationResponse, tags=["Server"])
async def set_server_channel(
    payload: ServerChannelRequest,
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Set app channel (stable/experimental)."""
    success, message = server.set_channel(payload.channel)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return OperationResponse(success=True, message=message)


@app.post("/server/auto-restart/enable", response_model=OperationResponse, tags=["Server"])
async def enable_auto_restart(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Enable automatic restart on crash"""
    success, message = server.control.enable_auto_restart()
    return OperationResponse(success=success, message=message)


@app.post("/server/auto-restart/disable", response_model=OperationResponse, tags=["Server"])
async def disable_auto_restart(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Disable automatic restart (crash loop protection)"""
    success, message = server.control.disable_auto_restart()
    return OperationResponse(success=success, message=message)


@app.post("/server/maintenance/enable", response_model=OperationResponse, tags=["Server"])
async def enable_maintenance(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Enter maintenance mode (blocks auto-start/auto-restart)"""
    success, message = server.enable_maintenance()
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return OperationResponse(success=True, message=message)


@app.post("/server/maintenance/disable", response_model=OperationResponse, tags=["Server"])
async def disable_maintenance(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Exit maintenance mode and restore normal behavior"""
    success, message = server.disable_maintenance()
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return OperationResponse(success=True, message=message)


# =============================================================================
# Installation & Updates
# =============================================================================


@app.post("/server/install", response_model=OperationResponse, tags=["Installation"])
async def install_server(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Install DayZ server files via SteamCMD"""
    success, output = server.install()
    if not success:
        raise HTTPException(status_code=500, detail=output)
    return OperationResponse(
        success=True,
        message="Server installed successfully",
        details={"output": output[-500:]},
    )


@app.post("/server/update", response_model=OperationResponse, tags=["Installation"])
async def update_server(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Update DayZ server files via SteamCMD"""
    success, output = server.update()
    if not success:
        raise HTTPException(status_code=500, detail=output)
    return OperationResponse(
        success=True,
        message="Server updated successfully",
        details={"output": output[-500:]},
    )


@app.post("/server/uninstall", response_model=OperationResponse, tags=["Installation"])
async def uninstall_server(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Uninstall DayZ server files (container-safe)."""
    success, message = server.uninstall()
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return OperationResponse(success=True, message=message)


# =============================================================================
# Configuration
# =============================================================================


@app.get("/config", tags=["Config"])
async def get_config(
    raw: bool = Query(False, description="Return unmasked secrets (requires auth)"),
    server: ServerManager = Depends(get_server),  # noqa: B008
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
) -> dict:
    """Get server configuration (raw cfg content)"""
    # Require auth for raw config
    if (
        raw
        and not API_AUTH_DISABLED
        and API_TOKEN
        and (not credentials or credentials.credentials != API_TOKEN)
    ):
        raise HTTPException(status_code=401, detail="Auth required for raw config")

    success, message, content = server.get_config(mask_secrets=not raw)
    if not success:
        raise HTTPException(status_code=404, detail=message)

    return {"success": True, "content": content}


@app.put("/config", response_model=OperationResponse, tags=["Config"])
async def update_config(
    payload: ConfigContent,
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Update server configuration (raw cfg content)"""
    success, message = server.update_config(payload.content)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return OperationResponse(success=True, message=message)


@app.get("/config/structured", tags=["Config"])
async def get_structured_config(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> dict:
    """Get structured configuration as JSON with field values"""
    success, message, config = server.get_server_config()
    if not success or config is None:
        raise HTTPException(status_code=400, detail=message)

    # Return config data (exclude internal fields)
    data = config.model_dump(exclude={"immutable_keys", "custom_lines"})
    return {"success": True, "message": message, "data": data}


@app.put("/config/structured", response_model=OperationResponse, tags=["Config"])
async def update_structured_config(
    payload: dict,
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Update structured configuration - saves to both JSON and cfg"""
    try:
        config = ServerConfig(**payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid config: {e}") from e

    success, message = server.save_server_config(config)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return OperationResponse(success=True, message=message)


@app.get("/config/schema", tags=["Config"])
async def get_config_schema(
    _auth: bool = Depends(verify_token),  # noqa: B008
) -> dict:
    """Get config field metadata for UI (descriptions, sections, types)"""
    # Get field info from Pydantic model
    fields_info = {}
    for name, field in ServerConfig.model_fields.items():
        if name in ("immutable_keys", "custom_lines"):
            continue

        # Determine field type
        annotation = field.annotation
        if annotation is int:
            field_type = "int"
        elif annotation is str:
            field_type = "str"
        elif annotation is bool:
            field_type = "bool"
        elif annotation is float:
            field_type = "float"
        elif (
            annotation is not None
            and hasattr(annotation, "__origin__")
            and annotation.__origin__ is list
        ):
            field_type = "list"
        else:
            field_type = "str"

        fields_info[name] = {
            "type": field_type,
            "default": field.default if field.default is not None else None,
            "description": ServerConfig.get_field_description(name),
        }

    return {
        "success": True,
        "fields": fields_info,
        "sections": ServerConfig.get_field_sections(),
        "descriptions": ServerConfig.get_all_descriptions(),
    }


# =============================================================================
# Steam
# =============================================================================


@app.get("/steam/status", response_model=CredentialsStatus, tags=["Steam"])
async def get_steam_status() -> CredentialsStatus:
    """Get Steam login status"""
    return SteamCredentials.get_status()


@app.post("/steam/login", response_model=OperationResponse, tags=["Steam"])
async def set_steam_login(
    payload: SteamLoginRequest,
    _auth: bool = Depends(verify_token),
) -> OperationResponse:
    """
    Set Steam username for cached credential login.

    Prerequisites:
    1. Run 'steamcmd +login YOUR_USERNAME' interactively (handles MFA)
    2. Once session is cached, call this endpoint with the username
    3. SteamCMD will reuse the cached session
    """
    success, message = SteamCredentials.set_username(payload.username)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return OperationResponse(success=True, message=message)


@app.post("/steam/test", response_model=LoginTestResult, tags=["Steam"])
async def test_steam_login(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> LoginTestResult:
    """Test Steam login with cached credentials"""
    return server.steamcmd.test_login()


@app.post("/steam/cached-config", response_model=ImportResult, tags=["Steam"])
async def import_steam_cached_config(
    payload: SteamCachedConfigRequest,
    _auth: bool = Depends(verify_token),  # noqa: B008
) -> ImportResult:
    """Import cached Steam credentials config.vdf and set required symlinks."""
    result = SteamCredentials.import_cached_config(payload.content, payload.username)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result


@app.post("/steam/cached-config/upload", response_model=ImportResult, tags=["Steam"])
async def import_steam_cached_config_upload(
    file: UploadFile = FILE_REQUIRED,
    username: str | None = Query(None, description="Optional username to write to ~/steamlogin"),
    _auth: bool = Depends(verify_token),  # noqa: B008
) -> ImportResult:
    """Import cached Steam credentials from a multipart file upload."""
    try:
        content_bytes = await file.read()
        content = content_bytes.decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {e}") from e

    result = SteamCredentials.import_cached_config(content, username)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result


@app.post("/steam/cached-config/raw", response_model=ImportResult, tags=["Steam"])
async def import_steam_cached_config_raw(
    request: Request,
    username: str | None = Query(None, description="Optional username to write to ~/steamlogin"),
    _auth: bool = Depends(verify_token),  # noqa: B008
) -> ImportResult:
    """Import cached Steam credentials from raw text/plain body."""
    try:
        body = await request.body()
        content = body.decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read request body: {e}") from e

    result = SteamCredentials.import_cached_config(content, username)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result


# =============================================================================
# Maps
# =============================================================================


@app.get("/maps", tags=["Maps"])
async def list_maps(
    _auth: bool = Depends(verify_token),  # noqa: B008
) -> dict:
    """List all available maps (official + community)"""
    from ..core.maps import MapManager

    manager = MapManager()
    maps = manager.list_available_maps()
    installed_templates = manager.get_installed_templates()

    return {
        "success": True,
        "maps": maps,
        "installed_templates": installed_templates,
    }


@app.get("/maps/{workshop_id}", tags=["Maps"])
async def get_map_info(
    workshop_id: str,
    _auth: bool = Depends(verify_token),  # noqa: B008
) -> dict:
    """Get info for a specific map"""
    manager = MapManager()
    info = manager.get_map_info(workshop_id)

    if not info:
        raise HTTPException(status_code=404, detail=f"Map not found: {workshop_id}")

    return {"success": True, "map": info}


@app.get("/maps/template/{template}", tags=["Maps"])
async def get_map_by_template(
    template: str,
) -> dict:
    """Get map info by mission template name (e.g. 'dayzOffline.enoch' returns Livonia info)"""
    manager = MapManager()
    info = manager.get_map_by_template(template)

    if not info:
        # Return minimal response if not found in registry
        return {
            "success": True,
            "map": {
                "name": template.replace("dayzOffline.", ""),
                "description": "Unknown map",
            },
        }

    return {"success": True, "map": info}


@app.post("/maps/{workshop_id}/install", response_model=OperationResponse, tags=["Maps"])
async def install_map(
    workshop_id: str,
    _auth: bool = Depends(verify_token),  # noqa: B008
) -> OperationResponse:
    """Install a custom map's mission files from GitHub"""
    manager = MapManager()
    success, message = manager.install_map(workshop_id)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return OperationResponse(success=True, message=message)


@app.delete("/maps/{workshop_id}", response_model=OperationResponse, tags=["Maps"])
async def uninstall_map(
    workshop_id: str,
    _auth: bool = Depends(verify_token),  # noqa: B008
) -> OperationResponse:
    """Remove a map's mission files"""
    manager = MapManager()
    success, message = manager.uninstall_map(workshop_id)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return OperationResponse(success=True, message=message)


# =============================================================================
# Admin Operations
# =============================================================================


@app.post("/admin/setup-mpmissions", response_model=OperationResponse, tags=["Admin"])
async def setup_mpmissions(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Copy pristine mpmissions if needed"""
    success, message = server.setup_mpmissions()
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return OperationResponse(success=True, message=message)


# =============================================================================
# Storage Management
# =============================================================================


@app.get("/admin/storage", tags=["Admin"])
async def get_storage_info(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> dict:
    """Get information about player/world storage directories"""
    return {"success": True, **server.get_storage_info()}


@app.delete("/admin/storage", response_model=OperationResponse, tags=["Admin"])
async def wipe_storage(
    storage_name: str | None = Query(
        None, description="Specific storage dir (e.g., 'storage_1') or omit for all"
    ),
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Wipe player/world storage (persistence data).

    WARNING: This deletes player inventories, bases, vehicles, etc.
    Server must be stopped before wiping.
    """
    success, message = server.wipe_storage(storage_name)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return OperationResponse(success=True, message=message)


# =============================================================================
# Server Files Cleanup
# =============================================================================


@app.get("/admin/cleanup", tags=["Admin"])
async def get_cleanup_info(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> dict:
    """Get information about files that can be cleaned up in /serverfiles"""
    return {"success": True, **server.get_cleanup_info()}


@app.post("/admin/cleanup", response_model=OperationResponse, tags=["Admin"])
async def cleanup_server_files(
    core_dumps: bool = Query(True, description="Remove core.* files"),
    crash_dumps: bool = Query(True, description="Remove .dmp/.mdmp files"),
    log_files: bool = Query(False, description="Remove .log/.rpt/.ADM files (careful!)"),
    temp_files: bool = Query(True, description="Remove .tmp/.temp files"),
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> OperationResponse:
    """Clean up unwanted files from /serverfiles (core dumps, crash dumps, etc.)"""
    success, message = server.cleanup_server_files(
        core_dumps=core_dumps,
        crash_dumps=crash_dumps,
        log_files=log_files,
        temp_files=temp_files,
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return OperationResponse(success=True, message=message)


# =============================================================================
# Logging Configuration
# =============================================================================


@app.get("/logs/files", tags=["Logs"])
async def list_log_files(
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> dict:
    """List available log files in /profiles"""
    return {"success": True, "files": server.list_log_files()}


@app.get("/logs", tags=["Logs"])
async def get_log_tail(
    filename: str | None = Query(None, description="Log file name (defaults to config logFile)"),
    bytes_count: int = Query(20000, description="Tail N bytes"),
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> dict:
    """Tail a log file."""
    success, message, content = server.read_log_tail(filename, bytes_count)
    if not success:
        raise HTTPException(status_code=404, detail=message)
    return {"success": True, "message": message, "content": content}


@app.get("/logs/stream", tags=["Logs"])
async def stream_log(
    filename: str | None = Query(None, description="Log file name (defaults to config logFile)"),
    _auth: bool = Depends(verify_token),  # noqa: B008
    server: ServerManager = Depends(get_server),  # noqa: B008
) -> StreamingResponse:
    """Stream a log file via server-sent events (basic)."""
    import asyncio
    from datetime import datetime
    from pathlib import Path

    # Resolve path
    path: Path | None = None
    if filename:
        path = PROFILES_DIR / filename if not filename.startswith("/") else Path(filename)
    else:
        success, _, cfg = server.get_server_config()
        if success and cfg is not None and getattr(cfg, "logFile", None):
            path = PROFILES_DIR / cfg.logFile
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    async def event_generator() -> AsyncIterator[str]:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if not line:
                        await asyncio.sleep(0.5)
                        continue
                    yield f"data: {line.rstrip()}\n\n"
        except Exception as e:
            yield f"data: [stream error] {e} ({datetime.now().isoformat()})\n\n"

    headers = {"Content-Type": "text/event-stream"}
    return StreamingResponse(event_generator(), headers=headers)


class HealthCheckFilter(logging.Filter):
    """Filter health check requests from access logs"""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return "/health" not in message


# Apply filter to uvicorn access logger
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
