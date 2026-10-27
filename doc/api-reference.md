# API Reference

Base path: `/api/v1`. Requests and responses use JSON. OpenAPI is available at `/api/docs` outside the `production` environment. Authentication uses a signed session cookie; same-origin browser requests include credentials automatically.

Mutating requests validate the `Origin` header. Set `ALLOWED_ORIGIN` to the exact public origin of the web application.

## Session and Users

- `GET /config/public`: returns only the store currency and whether catalog prices include tax. No session is required; no secrets are exposed.
- `POST /auth/login`: accepts `{"username":"clerk","password":"..."}` and sets a session cookie.
- `POST /auth/logout`: clears the current session.
- `GET /auth/me`: returns the authenticated user and role.
- `GET /users` (admin): lists accounts without password hashes.
- `POST /users` (admin): creates `{"username":"clerk2","password":"at-least-12-characters","role":"cashier"}`.
- `PATCH /users/{user_id}` (admin): updates `role`, `is_active`, or `password`. An administrator cannot deactivate their own account or the last active administrator.

Roles are `admin`, `supervisor`, and `cashier`. Authorization is enforced by the API, not only by the UI.

## Catalog

- `GET /books?q=text&isbn=978...&active=true&page=1&page_size=30`
- `POST /books`: creates a book with title, authors, optional ISBN, price, tax rate, and initial stock. Admin or supervisor only.
- `GET /books/{book_id}` and `PATCH /books/{book_id}`: read/update a book without changing historical sale snapshots.
- `GET /books/isbn/{isbn}`: look up a normalized ISBN.
- `DELETE /books/{book_id}`: archives the book; it does not erase sales history.

Paginated catalog responses have the shape `{ "items": [], "page": 1, "page_size": 30, "total": 0 }`. ISBN-10 and ISBN-13 values may include spaces or hyphens and are stored normalized.

## Sales and Returns

`POST /sales` requires an `Idempotency-Key` header containing 1-100 characters:

```json
{
  "items": [{"book_id": "UUID", "quantity": 2}],
  "payments": [
    {"method": "cash", "amount": "5.00", "cash_received": "5.00"},
    {"method": "card", "amount": "20.00"}
  ]
}
```

Payment methods are `cash`, `card`, and `other`. Payment amounts must equal the server-calculated total. Only cash payments accept `cash_received`, which must cover that payment amount; change is recorded. Repeating the same key and body replays the saved sale. Reusing a key with a different body returns `409`. Insufficient stock also returns `409` and makes no changes.

- `GET /sales?page=1&page_size=50` returns `{ "items": [], "page": 1, "page_size": 50, "total": 0 }`.
- `GET /sales/{sale_id}` returns the sale with each line's `returned_quantity` for partial-return UI.
- `POST /sales/{sale_id}/returns` (admin/supervisor):

```json
{
  "reason": "Customer return",
  "items": [{"sale_item_id": "UUID", "quantity": 1, "restock": true}]
}
```

The accumulated return quantity cannot exceed the sold quantity for a line. Sale details include `returned_quantity` per item so clients can show remaining returnable units. The API serializes concurrent returns on the sale record.

## Inventory and Reports

- `POST /inventory/adjustments` (admin/supervisor): `{"book_id":"UUID","quantity_delta":2,"reason":"Received copies"}`.
- `GET /inventory/movements?page=1&page_size=50` (admin/supervisor).
- `GET /reports/daily-sales` and `GET /reports/low-stock?threshold=3` (admin/supervisor).
- `GET /health/live` and `GET /health/ready` require no session.

The daily report separates `sold_total`, `refunded_total`, and net `total`. Returns are assigned to the day on which they are recorded.

## Errors

Validation and application errors use `application/problem+json` with `type`, `title`, `status`, and `detail`. Relevant status codes: `401` unauthenticated, `403` forbidden, `404` not found, `409` stock/idempotency/return conflict, and `422` invalid request or business rule. Internal stack traces are never returned.
