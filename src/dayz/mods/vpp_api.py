"""VPP API router (modular).

Provides a router for VPP Admin Tools endpoints and utilities to gate
availability based on whether the VPP mod is installed. Designed to be
plug-and-play from dayz.services.api.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.openapi.utils import get_openapi

from dayz.config.models import OperationResponse
from dayz.mods import vpp
from dayz.utils.steam_id import resolve_username_to_steam64, validate_steam64_id

APP_ID = 1828439124  # VPP Admin Tools Workshop ID


def _is_vpp_installed_app(app: FastAPI) -> bool:
    """Check via app.state.mods if VPP is installed (using mod ID)."""
    try:
        try:
            mods = app.state.mods
        except AttributeError:
            return False
        return any(m.id == str(APP_ID) for m in mods.list_installed_mods())
    except Exception:
        return False


def require_vpp_installed(request: Request) -> None:
    """Dependency: 404 if VPP is not installed."""
    if not _is_vpp_installed_app(request.app):
        raise HTTPException(status_code=404, detail="VPP mod not installed")


def build_router(verify_token: Callable[..., bool]) -> APIRouter:
    """Build and return the VPP router.

    Accepts the API's `verify_token` dependency to avoid circular imports.
    """
    router = APIRouter(tags=["VPP"])

    @router.post(
        "/vpp/password",
        response_model=OperationResponse,
        dependencies=[Depends(require_vpp_installed)],
    )
    async def set_vpp_password(  # noqa: D401
        payload: vpp.VPPPasswordRequest,
        _auth: bool = Depends(verify_token),
    ) -> OperationResponse:
        """Set VPPAdminTools password."""
        success, message = vpp.set_password(payload.password)
        if not success:
            raise HTTPException(status_code=400, detail=message)
        return OperationResponse(success=True, message=message)

    @router.post(
        "/vpp/superadmins",
        response_model=OperationResponse,
        dependencies=[Depends(require_vpp_installed)],
    )
    async def set_vpp_superadmins(  # noqa: D401
        payload: vpp.VPPSuperAdminsRequest,
        _auth: bool = Depends(verify_token),
    ) -> OperationResponse:
        """Set VPPAdminTools superadmin Steam64 IDs."""
        success, message = vpp.set_superadmins(payload.steam64_ids, payload.mode)
        if not success:
            raise HTTPException(status_code=400, detail=message)
        return OperationResponse(success=True, message=message)

    @router.get(
        "/vpp/superadmins",
        response_model=vpp.VPPSuperAdminsResponse,
        dependencies=[Depends(require_vpp_installed)],
    )
    async def get_vpp_superadmins(  # noqa: D401
        _auth: bool = Depends(verify_token),
    ) -> vpp.VPPSuperAdminsResponse:
        """Get VPPAdminTools superadmin Steam64 IDs."""
        success, result = vpp.get_superadmins()
        if not success:
            raise HTTPException(status_code=400, detail=result)
        return vpp.VPPSuperAdminsResponse(steam64_ids=cast(list[str], result))

    @router.post(
        "/vpp/steam-id/resolve",
        response_model=vpp.VPPSteamIdLookupResponse,
    )
    async def resolve_steam_username(  # noqa: D401
        payload: vpp.VPPSteamIdLookupRequest,
        _auth: bool = Depends(verify_token),
    ) -> vpp.VPPSteamIdLookupResponse:
        """Resolve Steam username or profile URL to Steam64 ID.

        This endpoint is accessible without VPP installed to help users
        find Steam IDs for configuration purposes.
        """
        success, steam64, message = resolve_username_to_steam64(payload.query)
        return vpp.VPPSteamIdLookupResponse(success=success, steam64_id=steam64, message=message)

    @router.post(
        "/vpp/steam-id/validate",
        response_model=vpp.VPPSteamIdLookupResponse,
    )
    async def validate_steam_id(  # noqa: D401
        payload: vpp.VPPSteamIdLookupRequest,
        _auth: bool = Depends(verify_token),
    ) -> vpp.VPPSteamIdLookupResponse:
        """Validate a Steam64 ID format.

        This endpoint is accessible without VPP installed to help users
        validate Steam IDs.
        """
        is_valid, message = validate_steam64_id(payload.query)
        # For validation, we return the input as steam64_id if valid
        return vpp.VPPSteamIdLookupResponse(
            success=is_valid,
            steam64_id=payload.query.strip() if is_valid else None,
            message=message,
        )

    return router


def attach_openapi_filter(app: FastAPI) -> None:
    """Wrap app.openapi to hide VPP endpoints when VPP is not installed."""

    def custom_openapi() -> dict:
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        if not _is_vpp_installed_app(app):
            paths = schema.get("paths", {})
            for p in list(paths.keys()):
                if p.startswith("/vpp/"):
                    del paths[p]
            tags = schema.get("tags", [])
            schema["tags"] = [t for t in tags if t.get("name") != "VPP"]
        return schema

    # Preserve potential previous wrappers by referencing original
    app.openapi = custom_openapi  # type: ignore[method-assign]
