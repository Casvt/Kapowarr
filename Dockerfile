ARG DISTRO=bookworm
ARG PYTHON=3.13

FROM python:${PYTHON}-slim-${DISTRO} AS python

# --- Build Stage ---
FROM rust:slim-${DISTRO} AS builder
WORKDIR /wheels

# Install Build Dependencies
RUN --mount=target=/var/lib/apt/lists,type=cache,sharing=private \
    --mount=target=/var/cache/apt,type=cache,sharing=private \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential libssl-dev libffi-dev pkg-config

# Copy Python From Python Stage
COPY --from=python /usr/local /usr/local
COPY --from=python /usr/lib /usr/lib
COPY --from=python /lib /lib
COPY --from=python /etc /etc

# Compile Wheels
COPY requirements.txt .
RUN pip3 wheel --wheel-dir=/wheels -r requirements.txt

# --- Runtime Stage ---
FROM python:${PYTHON}-slim-${DISTRO} AS runtime
WORKDIR /app
ARG TARGETARCH

# Install Runtime Dependencies
RUN --mount=target=/var/lib/apt/lists,type=cache,sharing=private \
    --mount=target=/var/cache/apt,type=cache,sharing=private \
    sed -i 's/Components: main/Components: main contrib non-free non-free-firmware/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    if [ "$TARGETARCH" != "amd64" ]; then \
        apt-get install -y --no-install-recommends unrar; \
    fi && \
    apt-get full-upgrade -y && \
    apt-get autoremove -y
COPY --from=tianon/gosu /gosu /usr/local/bin/

# Install Compiled Wheels
RUN --mount=from=builder,source=/wheels,target=/wheels \
    --mount=type=cache,target=/root/.cache/pip,sharing=private \
    pip3 install --no-index --find-links=/wheels -r /wheels/requirements.txt

RUN groupadd -g 1000 kapowarr && \
    useradd -u 1000 -g kapowarr -d /nonexistent -M -s /bin/bash kapowarr && \
    mkdir -p /app/db /app/logs /app/temp_downloads

COPY --chmod=755 . .
RUN if [ "$TARGETARCH" != "amd64" ]; then \
        rm -f /app/backend/lib/rar_linux_64 && \
        ln -s /usr/bin/unrar /app/backend/lib/rar_linux_64; \
    fi

ENV PUID=0 \
    PGID=0 \
    TZ=UTC

EXPOSE 5656

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python3", "/app/Kapowarr.py", "--LogFolder", "/app/logs"]
