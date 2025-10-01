# TODO: prompt user to enter container user for postgres

# Dump
docker exec my_postgres_container pg_dumpall -U postgres \
  > /var/lib/postgresql/backups/backup-{date}.sql

# Stop old container
docker compose down postgres

# Pull latest change
docker compose pull postgres

# Build changes
docker compose build postgres

# Drop data volume
docker volume rm project_database

# Upgrade image version in docker-compose.yml
# Start new container
docker compose up -d postgres

# Restore
docker exec -i new_postgres_container psql -U postgres \
  < /var/lib/postgresql/backups/backup-{date}.sql

# Alter collections version
ALTER DATABASE keycloak REFRESH COLLATION VERSION
