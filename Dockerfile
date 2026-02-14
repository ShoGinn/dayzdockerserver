# syntax=docker/dockerfile:1.4
# =============================================================================
# DayZ Server - Multi-stage Dockerfile (Modernized)
# =============================================================================
# Based on official BI documentation and SteamCMD best practices
# https://community.bistudio.com/wiki/DayZ:Hosting_a_Linux_Server
# https://developer.valvesoftware.com/wiki/SteamCMD
#
# Build arguments:
#   USER_ID: UID for the non-root user (default: 1000)
#
# Stages:
#   - web-build: Build the frontend
#   - base: Common dependencies, SteamCMD, Python
#   - api: Management API (runs as user with sudo)
#   - server: DayZ server with supervisor
#   - web: Nginx serving frontend with API proxy
# =============================================================================

# Build argument for user ID (can be overridden at build time)
ARG USER_ID=1000

# -----------------------------------------------------------------------------
# Web build stage: Build the React frontend
# -----------------------------------------------------------------------------
FROM node:lts-slim AS web-build

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

RUN corepack enable

WORKDIR /web

# Copy package files first for better layer caching
COPY web/package.json web/pnpm-lock.yaml* ./

# Install dependencies with cache mount
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile

# Copy source files and build
COPY web/ ./
RUN pnpm run build

# -----------------------------------------------------------------------------
# Base stage: Common to all containers
# -----------------------------------------------------------------------------
FROM ubuntu:24.04 AS base

# Re-declare ARG after FROM
ARG USER_ID=1000

ENV DEBIAN_FRONTEND=noninteractive

# Add i386 architecture for SteamCMD
RUN dpkg --add-architecture i386

# Install system dependencies with apt cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    # 32-bit libraries for SteamCMD
    lib32gcc-s1 \
    lib32stdc++6 \
    # DayZ server libraries
    libcurl4 \
    libcap2 \
    # Utilities
    bash \
    ca-certificates \
    curl \
    jq \
    locales \
    procps \
    sudo \
    tar \
    wget \
    # Python
    python3 \
    python3-pip \
    # User management tools
    passwd \
    # Tini for proper PID 1 handling
    tini \
    && rm -rf /var/lib/apt/lists/*

# Configure locale
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen

ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8

# Create non-privileged user with configurable UID
# MUST be done BEFORE SteamCMD installation so chown works
# Ubuntu 24.04 may already have GID/UID 1000, so check first
# Note: We use numeric IDs (${USER_ID}) in chown/COPY commands because
#       the actual username might be 'ubuntu' or other existing user
RUN getent group ${USER_ID} >/dev/null || groupadd -g ${USER_ID} user; \
    getent passwd ${USER_ID} >/dev/null || useradd -l -u ${USER_ID} -m -g ${USER_ID} -s /bin/bash user; \
    echo "user ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/user && \
    chmod 0440 /etc/sudoers.d/user

# Install SteamCMD
RUN mkdir -p /opt/steamcmd \
    && cd /opt/steamcmd \
    && curl -sqL "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz" | tar zxf - \
    && chmod +x /opt/steamcmd/steamcmd.sh \
    && printf '#!/bin/bash\nexec /opt/steamcmd/steamcmd.sh "$@"\n' > /usr/local/bin/steamcmd \
    && chmod +x /usr/local/bin/steamcmd \
    && /opt/steamcmd/steamcmd.sh +quit || true \
    && chown -R ${USER_ID}:${USER_ID} /opt/steamcmd

# Install uv for Python package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install Python dependencies
WORKDIR /tmp/build
COPY pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --break-system-packages .
WORKDIR /

# Create directory structure (runtime volumes will be mounted over most of these)
# Only create directories needed at build time for COPY operations
RUN mkdir -p \
    /app \
    /scripts \
    && chown -R ${USER_ID}:${USER_ID} /app /scripts

# Copy shared Python modules
COPY --chown=${USER_ID}:${USER_ID} src/dayz/ /app/dayz/
ENV PYTHONPATH=/app

# Set environment variables
ENV HOME=/home/user \
    STEAMCMD_DIR=/opt/steamcmd \
    PYTHONUNBUFFERED=1

# Add metadata labels
LABEL org.opencontainers.image.title="DayZ Server Base" \
    org.opencontainers.image.description="Base image for DayZ dedicated server" \
    org.opencontainers.image.vendor="Your Organization"

# -----------------------------------------------------------------------------
# API stage: Management API + Web UI
# -----------------------------------------------------------------------------
FROM base AS api

# Re-declare ARG after FROM
ARG USER_ID=1000

# Install additional API dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    git \
    xmlstarlet \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# NOTE: Run as non-root user for security
# Use sudo in Python code when privileged operations are needed
USER ${USER_ID}

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsSL http://localhost:8080/health || exit 1

CMD ["python3", "-m", "uvicorn", "dayz.services.api:app", "--host", "0.0.0.0", "--port", "8080"]

LABEL org.opencontainers.image.title="DayZ Server API" \
    org.opencontainers.image.description="Management API for DayZ dedicated server"

# -----------------------------------------------------------------------------
# Server stage: DayZ server with supervisor
# -----------------------------------------------------------------------------
FROM base AS server

# Re-declare ARG after FROM
ARG USER_ID=1000

USER ${USER_ID}
WORKDIR /home/user

# The supervisor manages DayZServer lifecycle
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python3", "-m", "dayz.services.supervisor"]


LABEL org.opencontainers.image.title="DayZ Server" \
    org.opencontainers.image.description="DayZ dedicated game server with supervisor"

# -----------------------------------------------------------------------------
# Web stage: Nginx serving built frontend with proxy to API
# -----------------------------------------------------------------------------
FROM nginx:alpine AS web

# Copy built frontend assets
COPY --from=web-build /web/dist /usr/share/nginx/html

# Copy Nginx configuration
COPY web/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

LABEL org.opencontainers.image.title="DayZ Server Web UI" \
    org.opencontainers.image.description="Web interface for DayZ server management"