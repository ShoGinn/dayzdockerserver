# syntax=docker/dockerfile:1.4@sha256:9ba7531bd80fb0a858632727cf7a112fbfd19b17e94c4e84ced81e24ef1a0dbc

ARG USER_ID=1000
ARG GROUP_ID=1000
ARG UBUNTU_IMAGE=ubuntu:24.04@sha256:561618e2c15bf2397621dd04f96926663a3b5616c189cf7e38db7e82f5c538ea
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.5@sha256:e85be844203885286c60ffad8a858d48afb6c5a5c237ca0e67f12e74b8f174b1
ARG STEAMCMD_SHA256=cebf0046bfd08cf45da6bc094ae47aa39ebf4155e5ede41373b579b8f1071e7c

FROM ${UV_IMAGE} AS uv-bin

FROM --platform=$BUILDPLATFORM node:24.20.0-slim@sha256:ba849c60be29959425b8734d57b8b4b7d56f98edd9504c9af091d5281095a71e AS web-build
ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable
WORKDIR /web
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm run build

FROM --platform=linux/amd64 ${UBUNTU_IMAGE} AS python-deps
ENV DEBIAN_FRONTEND=noninteractive \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends ca-certificates python3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=uv-bin /uv /usr/local/bin/uv
WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

FROM --platform=linux/amd64 ${UBUNTU_IMAGE} AS steamcmd-download
ARG STEAMCMD_SHA256
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends ca-certificates curl tar \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/steamcmd
RUN curl --fail --show-error --location --proto '=https' --tlsv1.2 \
      https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz \
      --output /tmp/steamcmd.tar.gz \
    && echo "${STEAMCMD_SHA256}  /tmp/steamcmd.tar.gz" | sha256sum --check --strict \
    && tar --extract --gzip --file /tmp/steamcmd.tar.gz --directory /opt/steamcmd \
    && test -x /opt/steamcmd/steamcmd.sh

FROM --platform=linux/amd64 ${UBUNTU_IMAGE} AS base
ARG USER_ID
ARG GROUP_ID
ENV DEBIAN_FRONTEND=noninteractive
RUN dpkg --add-architecture i386
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
      bash ca-certificates lib32gcc-s1 lib32stdc++6 libcap2 libcurl4 locales passwd procps python3 tini \
    && rm -rf /var/lib/apt/lists/*
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
RUN if ! getent group ${GROUP_ID} >/dev/null; then groupadd --gid ${GROUP_ID} user; fi \
    && if ! getent passwd ${USER_ID} >/dev/null; then useradd --uid ${USER_ID} --gid ${GROUP_ID} --home-dir /home/user --shell /bin/bash user; fi \
    && mkdir -p /app /control /files /home/user /mpmissions-upstream /profiles /serverfiles \
    && chown -R ${USER_ID}:${GROUP_ID} /app /control /home/user /mpmissions-upstream /profiles /serverfiles
COPY --from=steamcmd-download --chown=${USER_ID}:${GROUP_ID} /opt/steamcmd /opt/steamcmd
COPY --from=python-deps /opt/venv /opt/venv
RUN printf '#!/bin/bash\nexec /opt/steamcmd/steamcmd.sh "$@"\n' > /usr/local/bin/steamcmd \
    && chmod 0755 /usr/local/bin/steamcmd
COPY --chown=${USER_ID}:${GROUP_ID} src/dayz/ /app/dayz/
ENV HOME=/home/user \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8 \
    PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    STEAMCMD_DIR=/opt/steamcmd
LABEL org.opencontainers.image.title="DayZ Server Base" \
      org.opencontainers.image.description="Runtime for the DayZ server and management API"

FROM base AS api
ARG USER_ID
ARG GROUP_ID
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
USER ${USER_ID}:${GROUP_ID}
WORKDIR /app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3).read()"]
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python3", "-m", "uvicorn", "dayz.services.api:app", "--host", "0.0.0.0", "--port", "8080"]
LABEL org.opencontainers.image.title="DayZ Server API"

FROM base AS server
ARG USER_ID
ARG GROUP_ID
USER ${USER_ID}:${GROUP_ID}
WORKDIR /home/user
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python3", "-m", "dayz.services.supervisor"]
LABEL org.opencontainers.image.title="DayZ Server"

FROM nginx:1.31.4-alpine@sha256:db35bfc6b2951e7f8a72db5db120288c127ffaeeb4a6d4b95a26fead017d5913 AS web
COPY --from=web-build /web/dist /usr/share/nginx/html
COPY web/nginx-main.conf /etc/nginx/nginx.conf
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["wget", "--no-verbose", "--tries=1", "--spider", "http://127.0.0.1:8080/"]
ENTRYPOINT []
CMD ["nginx", "-g", "daemon off;"]
LABEL org.opencontainers.image.title="DayZ Server Web UI"
