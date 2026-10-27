# Installation, Operations, and Recovery

## Host Prerequisite

Docker Engine or Docker Desktop with Docker Compose v2. Do not install Python, Node.js, npm, or PostgreSQL. The user running the commands must be authorized to access the Docker daemon. The first build requires internet access.

## First-Time Setup

From the repository root, create the local environment file:

```bash
cp .env.example .env
```

Edit `.env`: set a unique `POSTGRES_PASSWORD`, an `APP_SECRET` of at least 32 characters, and a `BOOTSTRAP_ADMIN_PASSWORD` of at least 12 characters. Set the initial admin username and password. The blank secret placeholders intentionally prevent startup until configured. The database URL is built from separate credentials, so reserved characters in the database password are supported. For local HTTP, keep `APP_ENV=development` and `COOKIE_SECURE=false`. For production, use platform-managed secrets, `APP_ENV=production`, `COOKIE_SECURE=true`, HTTPS, and the exact public `ALLOWED_ORIGIN`.

Start the application:

```bash
sh scripts/up.sh
```

The script generates the frontend lockfile inside Docker if it is missing, then runs `docker compose up --build -d`. Compose waits for PostgreSQL, runs the `init` service to apply Alembic migrations and create the first administrator, then starts the API and web service. The bootstrap safely skips an already-initialized database.

Open `http://localhost:8080`, or the port configured by `WEB_PORT`. Check `docker compose ps` and `docker compose logs -f` if a service is unhealthy.

## Development

```bash
docker compose -f compose.yaml -f compose.dev.yaml --profile dev up --build
```

Vite is available at port 5173 and FastAPI at port 8000. Source is bind-mounted for hot reload; dependencies remain inside Docker images/volumes. The development overlay does not start the production API or web containers.

When `package-lock.json` changes, the development container detects the new lockfile hash and runs `npm ci` once before starting Vite. Normal restarts reuse the existing dependency volume.

## Tests and Quality Checks

```bash
make test
make lint
docker compose --profile test run --build --rm frontend-tests npm run build
docker compose build
```

The test profile uses a separate ephemeral PostgreSQL service without a persistent volume. Never point destructive tests at a store database.
The `make test` target stops the test database container after the backend suite, whether it succeeds or fails.

## Upgrades

1. Make an external backup and verify that it is readable.
2. Obtain the reviewed application version and build the images.
3. Run `docker compose --profile tools run --rm migrate` to apply migrations explicitly before a controlled deployment. The normal `up` flow also runs the idempotent `init` service.
4. Restart and inspect `docker compose ps`, health checks, and logs.
5. Keep a rollback plan compatible with the new schema.

## Backup and Restore

Create a logical dump. The output file is written to the current host directory; protect it and copy it off the server:

```bash
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > booker-tpv-backup.sql
```

Restore into an empty, isolated database (this destroys data in that target database):

```bash
docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" "$POSTGRES_DB"' < booker-tpv-backup.sql
```

Do not restore over production without an approved procedure. Rehearse recovery in an isolated environment and document retention, encryption, RPO, and RTO.

## Stop and Remove Data

`docker compose down` stops containers and preserves data. `docker compose down -v` also deletes the PostgreSQL volume; use it only for disposable environments after confirming the data is not needed.

## Commercial Limitations

Receipts are informational, not certified invoices. Before commercial use, confirm jurisdiction, tax, numbering, and invoicing/POS software regulations with qualified counsel. Configure HTTPS and validate the application with the actual terminals and peripherals.
