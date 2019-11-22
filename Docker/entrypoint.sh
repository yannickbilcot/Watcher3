#!/bin/sh

set -e

# Set user and group IDs if they were specified, else 0 (root)
APPID="${APP_UID:=0}:${APP_GID:=0}"

# Change ownership of config and app dirs
chown -R $APPID /config /opt/watcher3

# Check to see if the docker config folder contains default names, and rename and organise them.

OLD_CFG=/config/config.cfg
if [ -f "$OLD_CFG" ]; then
    echo "$OLD_CFG exists, renaming to watcher.cfg."
    mv /config/config.cfg /config/watcher.cfg
fi

OLD_DB=/config/watcher.sqlite
if [ -f "$OLD_DB" ]; then
    echo "$OLD_DB exists, renaming to database.sqlite and moving into db folder."
    mkdir /config/db
    mv /config/watcher.sqlite /config/db/database.sqlite
fi

# Exec the CMD as the app user
cd /opt/watcher3
exec su-exec $APPID python3 "$@" --userdata /config --posters /config/posters --plugins /config/plugins
