#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# API Container Entrypoint — Volume Initialization
# =============================================================================
# Ensures Docker named volume mount points are owned by the container user
# before handing off to the CMD (uvicorn). On subsequent restarts the stat
# check makes this a no-op — no expensive recursive walks.
# =============================================================================

MOUNT_POINTS=(
    /home/user
    /serverfiles
    /mpmissions-upstream
    /profiles
    /control
)

CURRENT_UID="$(id -u)"
CURRENT_GID="$(id -g)"

echo "[entrypoint] Initializing volumes..."

for mp in "${MOUNT_POINTS[@]}"; do
    owner="$(stat -c %u "$mp" 2>/dev/null || echo "unknown")"
    if [ "$owner" != "$CURRENT_UID" ]; then
        echo "[entrypoint] Fixing ownership: $mp ($owner -> $CURRENT_UID)"
        sudo chown "$CURRENT_UID:$CURRENT_GID" "$mp"
    fi
done

# IPC socket directory needs world-accessible permissions so both api and
# server containers (potentially different UIDs) can read/write the socket.
chmod 777 /control

# Create required subdirectories (no sudo needed — mount points already owned)
mkdir -p \
    /home/user/.steam \
    /serverfiles/steamapps/workshop/content/221100 \
    /serverfiles/keys \
    /serverfiles/mpmissions \
    /profiles/battleye \
    /control

echo "[entrypoint] Volume initialization complete."

exec "$@"
