FROM alpine:3.8

ENV LANG="en_US.utf8" APP_NAME="watcher3" IMG_NAME="watcher3"

RUN apk add --no-cache bash curl git nano vim ca-certificates python3
RUN rm -rf /tmp/* /var/tmp/*

# Create a group and user
RUN addgroup -S watcher && adduser -S watcher -G watcher
# Tell docker that all future commands should run as the watcher user
USER watcher

COPY . /opt/$APP_NAME

WORKDIR /opt/watcher3

VOLUME /config
EXPOSE 9090

CMD python3 /opt/$APP_NAME/watcher.py -c /config/watcher.cfg -l /config/logs/ --db /config/db/database.sqlite --plugins /config/plugins/ --posters /config/posters

