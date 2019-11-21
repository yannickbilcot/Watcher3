#!/bin/sh

set -e

# Check to see if the docker config folder contains hurricane/watcher3 names, and rename them.

OLD_CFG=/config/watcher.cfg
if [ -f "$OLD_CFG" ]; then
    echo "$OLD_CFG exists, renaming to config.cfg."
    mv /config/watcher.cfg /config/config.cfg
fi

OLD_DB=/config/db/database.sqlite
if [ -f "$OLD_DB" ]; then
    echo "$OLD_DB exists, renaming to watcher.sqlite and moving to root of config folder."
    mv /config/db/database.sqlite /config/watcher.sqlite
    rmdir /config/db
fi

# Set user and group IDs if they were specified, else 0 (root)
APPID="${APP_UID:=0}:${APP_GID:=0}"

# Change ownership of config and app dirs
chown -R ${APPID} /config /opt/watcher3

# Exec the CMD as the app user
exec su-exec ${APPID} "$@"
