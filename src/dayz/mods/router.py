"""
Mods Management Router

FastAPI router for all mod-related operations:
- List mods
- Install/remove mods
- Activate/deactivate mods
- Set mod mode
- Bulk operations
- Update all mods
"""

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from dayz.config.models import (
    BulkModRequest,
    ModListResponse,
    ModResponse,
)
from dayz.core.mods import ModManager, ModOperationResult


def create_router(
    get_mods_dependency: Callable[..., Any],
    verify_token_dependency: Callable[..., Any],
) -> APIRouter:
    """Create and configure the mods router.

    Args:
        get_mods_dependency: Dependency function that returns ModManager
        verify_token_dependency: Dependency function that verifies authentication

    Returns:
        Configured APIRouter instance
    """
    router = APIRouter(prefix="/mods", tags=["Mods"])

    @router.get("", response_model=ModListResponse)
    async def list_mods(
        active_only: bool = Query(False, description="Only return active mods"),
        mods: ModManager = Depends(get_mods_dependency),  # noqa: B008
    ) -> ModListResponse:
        """List installed mods"""
        mod_list = mods.list_active_mods() if active_only else mods.list_installed_mods()
        return ModListResponse(
            mods=[
                ModResponse(
                    id=m.id,
                    name=m.name,
                    url=m.url,
                    size=m.size,
                    active=m.active,
                )
                for m in mod_list
            ],
            count=len(mod_list),
        )

    @router.post("/install/{mod_id}", response_model=ModOperationResult)
    async def install_mod(
        mod_id: str,
        _auth: bool = Depends(verify_token_dependency),  # noqa: B008
        mods: ModManager = Depends(get_mods_dependency),  # noqa: B008
    ) -> ModOperationResult:
        """Install a workshop mod"""
        result = mods.install_mod(mod_id)
        if not result.success:
            raise HTTPException(status_code=500, detail=result.message)
        return result

    @router.delete("/{mod_id}", response_model=ModOperationResult)
    async def remove_mod(
        mod_id: str,
        _auth: bool = Depends(verify_token_dependency),  # noqa: B008
        mods: ModManager = Depends(get_mods_dependency),  # noqa: B008
    ) -> ModOperationResult:
        """Remove a mod"""
        result = mods.remove_mod(mod_id)
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        return result

    @router.post("/{mod_id}/activate", response_model=ModOperationResult)
    async def activate_mod(
        mod_id: str,
        _auth: bool = Depends(verify_token_dependency),  # noqa: B008
        mods: ModManager = Depends(get_mods_dependency),  # noqa: B008
    ) -> ModOperationResult:
        """Activate a mod"""
        result = mods.activate_mod(mod_id)
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        return result

    @router.post("/{mod_id}/deactivate", response_model=ModOperationResult)
    async def deactivate_mod(
        mod_id: str,
        _auth: bool = Depends(verify_token_dependency),  # noqa: B008
        mods: ModManager = Depends(get_mods_dependency),  # noqa: B008
    ) -> ModOperationResult:
        """Deactivate a mod"""
        result = mods.deactivate_mod(mod_id)
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        return result

    @router.post("/{mod_id}/mode", response_model=ModOperationResult)
    async def set_mod_mode(
        mod_id: str,
        mode: str = Query(..., description="'server' or 'client'"),
        _auth: bool = Depends(verify_token_dependency),  # noqa: B008
        mods: ModManager = Depends(get_mods_dependency),  # noqa: B008
    ) -> ModOperationResult:
        """Set explicit mod mode override (server/client)."""
        if mode not in ("server", "client"):
            raise HTTPException(status_code=400, detail="Mode must be 'server' or 'client'")
        result = mods.set_mod_mode(mod_id, mode)  # type: ignore
        if not result.success:
            raise HTTPException(status_code=400, detail=result.message)
        return result

    @router.post("/bulk", response_model=ModOperationResult)
    async def bulk_install_mods(
        payload: BulkModRequest,
        _auth: bool = Depends(verify_token_dependency),
        mods: ModManager = Depends(get_mods_dependency),  # noqa: B008
    ) -> ModOperationResult:
        """Install and activate multiple mods at once"""
        if not payload.mod_ids:
            raise HTTPException(status_code=400, detail="No mod IDs provided")

        return mods.bulk_install_activate(payload.mod_ids)

    @router.post("/update-all", response_model=ModOperationResult)
    async def update_all_mods(
        _auth: bool = Depends(verify_token_dependency),
        mods: ModManager = Depends(get_mods_dependency),  # noqa: B008
    ) -> ModOperationResult:
        """Update all installed mods"""
        installed = mods.list_installed_mods()
        if not installed:
            return ModOperationResult(success=True, message="No mods to update")

        mod_ids = [m.id for m in installed]
        success, output = mods.steamcmd.update_mods(mod_ids)

        if not success:
            raise HTTPException(status_code=500, detail=output[-500:])

        return ModOperationResult(
            success=True,
            message=f"Updated {len(mod_ids)} mod(s)",
        )

    return router
