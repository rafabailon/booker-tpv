# Architecture

## Services

```text
Browser --HTTP/HTTPS--> web (Nginx + SPA assets)
                            | /api/*, private network
                            v
                         api (FastAPI) ------> db (PostgreSQL 18)
                                                    |
                                                 pgdata
```

- `web` serves the production React assets and proxies `/api/` to FastAPI. Development uses `web-dev` with Vite.
- `api` validates sessions, roles, requests, payments, inventory, and transactions. Client-supplied totals are never trusted.
- `db` does not publish a host port. The `pgdata` volume is mounted at `/var/lib/postgresql`, the persistent-data path used by the official PostgreSQL 18 image.
- `init` waits for PostgreSQL, applies Alembic migrations, and creates the first administrator before either API service starts. The bootstrap is a no-op once users exist.
- `migrate` is an explicit one-off service in the `tools` profile for controlled migration runs.
- `frontend-lock` generates `frontend/package-lock.json` using Node inside Docker; image builds install with `npm ci`.
- `web-dev` keeps dependencies in a named volume and reruns `npm ci` only when the lockfile hash changes.
- `test-db`, `backend-tests`, and `frontend-tests` belong to the `test` profile.

Application services communicate over the Compose `backend` network. Only the web service publishes a port. Put a TLS-enabled reverse proxy or load balancer in front of production deployments and restrict host exposure.

## Checkout Consistency

The backend calculates prices and taxes, consolidates repeated book IDs, locks catalog rows in stable order, and validates stock. Sale, lines, payments, stock movements, and audit events commit in one transaction. An `Idempotency-Key` and request fingerprint make retries safe and reject reuse of a key with a different body.

Returns are compensating records; completed sales are never deleted. Stock is restored only for items marked for restocking. Previously returned quantities are checked while the sale and its lines are locked, preventing duplicate refunds.

## Compose Profiles

- Default: production API, web, database, and the one-off `init` dependency.
- `dev`: combine `compose.yaml` with `compose.dev.yaml` and enable `api-dev`/`web-dev` for mounted source and hot reload. The overlay places production web/API services in the `production` profile so they do not start alongside development services.
- `tools`: explicit migration and lockfile-generation utilities.
- `test`: an ephemeral PostgreSQL database and isolated test containers.

Compose profiles can be combined with unprofiled services. The test database has no persistent volume and is separate from application data.

## Security and Data

Sessions use signed, HTTP-only cookies with `SameSite=Strict`; the Secure flag is configurable. Mutating requests validate `Origin` against `ALLOWED_ORIGIN`. Production Nginx rate-limits login to 10 requests per minute with a burst of 5; the Vite development server does not apply this limit. Authorization is enforced by the API. Card payments store only the method and optional external reference; PAN, CVV, PIN, and banking credentials are never stored.

Request logs contain a request ID, method, path, and status code, but no credentials or request bodies. Backups must be stored outside the database volume and server. A volume is not a backup. Test migrations and restorations before production use.

