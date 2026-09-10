ARG POSTGRES_VERSION=18
FROM postgres:${POSTGRES_VERSION}-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends awscli ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY deploy/backup/backup.sh /usr/local/bin/erp-backup
RUN chmod 755 /usr/local/bin/erp-backup
ENTRYPOINT ["bash", "/usr/local/bin/erp-backup"]
