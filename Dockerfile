FROM alpine:3.10.3

ENV LANG="en_US.utf8" APP_NAME="watcher3" IMG_NAME="watcher3" PATH="/opt/watcher3:$PATH"

RUN apk add --no-cache bash curl git nano vim ca-certificates python3 su-exec

COPY . /opt/$APP_NAME

RUN rm -rf /tmp/* /var/tmp/* /opt/$APP_NAME/entrypoint.sh /opt/$APP_NAME/Docker

WORKDIR /opt/watcher3

COPY Docker/entrypoint.sh /

RUN chmod +x /entrypoint.sh && mkdir /config

VOLUME /config

EXPOSE 9090

ENTRYPOINT ["/entrypoint.sh"]

CMD ["watcher.py"]

