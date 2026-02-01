#!/usr/bin/env bash

set -e

PUID=${PUID}
PGID=${PGID}
ID_CACHE_FILE="/app/.id_cache"

# Stay as root user
if [ "$PUID" = "0" ]; then
    echo "Running as root user..."
    exec "$@"

# Switch to non-root user
else
    echo "Updating kapowarr to ($PUID:$PGID)..."

    # Group
    if [ "$(id -g kapowarr)" != "$PGID" ]; then 
        groupmod -o -g "$PGID" kapowarr
    fi
    # User
    if [ "$(id -u kapowarr)" != "$PUID" ]; then
        usermod -o -u "$PUID" -g "$PGID" kapowarr
    fi

    # Mount permissions
    CURRENT_ID="${PUID}:${PGID}"
    if [ -f "$ID_CACHE_FILE" ] && [ "$(cat "$ID_CACHE_FILE")" = "$CURRENT_ID" ]; then
        echo "Permissions match. Skipping chown."
    else
        echo "Permission mismatch or first run. Updating permissions..."
        chown -R kapowarr:kapowarr /app
        echo "$CURRENT_ID" > "$ID_CACHE_FILE"
    fi

    # Drop Privileges
    echo "Dropping privileges to kapowarr ($PUID:$PGID)..."
    exec gosu kapowarr "$@"
fi