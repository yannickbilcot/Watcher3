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
    cp /config/config.cfg /config/watcher.cfg
        if [-f "/config/watcher.cfg" ]; then
            echo "We seem to have successfully moved and renamed the old config, backing up original and tidying up."
                if [-z "/config/backups" ]; then
                mkdir /config/backups
                fi
            cp /config/config.cfg /config/backups/config.cfg
            rm /config/config.cfg
        fi
fi

OLD_DB=/config/watcher.sqlite
if [ -f "$OLD_DB" ]; then
    echo "$OLD_DB exists, renaming to database.sqlite and moving into db folder."
    mkdir /config/db
    cp /config/watcher.sqlite /config/db/database.sqlite
        if [-f "/config/db/database.sqlite"]; then
            echo "We seem to have successfully moved and renamed the old db, backing up original and tidying up."
                if [-z "/config/backups" ]; then
                mkdir /config/backups
                fi
            cp /config/watcher.sqlite /config/backups/watcher.sqlite
            rm /config/watcher.sqlite
        fi   
fi

# Exec the CMD as the app user
cd /opt/watcher3
exec su-exec $APPID python3 "$@" --userdata /config --posters /config/posters --plugins /config/plugins
