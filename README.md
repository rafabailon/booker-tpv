# Booker TPV

Booker TPV is a web-based point-of-sale system for independent bookshops. It combines a React/TypeScript frontend, a FastAPI backend, and PostgreSQL, orchestrated with Docker Compose. Python, Node.js, npm, and PostgreSQL do not need to be installed on the host: Docker Engine and the Compose v2 plugin are enough.

## Quick Start

1. Copy `.env.example` to `.env`. Set unique values for `POSTGRES_PASSWORD`, `APP_SECRET` (at least 32 characters), and `BOOTSTRAP_ADMIN_PASSWORD` (at least 12 characters). Empty placeholders prevent startup until the secrets are configured. Keep `.env` out of version control.
2. Set `BOOTSTRAP_ADMIN_USERNAME` and `BOOTSTRAP_ADMIN_PASSWORD` to create the first administrator.
3. Start the application:

   ```bash
   sh scripts/up.sh
   ```

   The script generates `frontend/package-lock.json` inside Docker if it is missing, then builds and starts the stack. Compose waits for PostgreSQL, applies the Alembic migrations, creates the first administrator, and only then starts the API and web server. Administrator bootstrap does not run again once users exist.

Open [http://localhost:8080](http://localhost:8080). The port can be changed with `WEB_PORT`. The first start requires internet access to download base images and dependencies. Docker must be running and the user must have permission to access its daemon.

## Development

```bash
docker compose -f compose.yaml -f compose.dev.yaml --profile dev up --build
```

Vite is available at [http://localhost:5173](http://localhost:5173) and FastAPI at [http://localhost:8000](http://localhost:8000). Source code is mounted into the containers for hot reload. Migrations and first-administrator creation are handled by the `init` service.

## Tests and Quality

```bash
make test
make lint
docker compose --profile test run --build --rm frontend-tests npm run build
docker compose build
```

Backend tests use an ephemeral PostgreSQL service from the `test` profile, independent of the persistent database. The `make test` target stops that container when the backend suite finishes, even if it fails.

## Operations

- `docker compose ps`: service status.
- `docker compose logs -f`: follow logs.
- `docker compose --profile tools run --rm migrate`: apply migrations explicitly.
- `docker compose down`: stop services while keeping PostgreSQL data.
- Avoid `docker compose down -v` for routine cleanups: it permanently deletes the database volume.

PostgreSQL is not published to the host. In production, use HTTPS, set `APP_ENV=production`, `COOKIE_SECURE=true`, and `ALLOWED_ORIGIN` to the exact public origin. Use platform-managed secrets instead of development credentials. `PRICES_INCLUDE_TAX` controls whether catalog prices include VAT. Receipts are informational, not certified invoices; verify local tax and invoicing requirements before commercial use.

## Documentation

- [Architecture](doc/architecture.md)
- [API Reference](doc/api-reference.md)
- [Installation and Recovery Guide](doc/installation-guide.md)
- [User Manual](doc/user-manual.md)
