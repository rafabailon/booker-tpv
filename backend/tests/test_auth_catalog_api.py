"""Authentication, user administration, and catalog API tests."""

from fastapi.testclient import TestClient

from app.config import get_settings


def book_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "isbn": "978-0-306-40615-7",
        "title": "El nombre del viento",
        "authors": "Patrick Rothfuss",
        "publisher": "Plaza & Janés",
        "category": "Fantasía",
        "price": "12.50",
        "tax_rate": "4.00",
        "stock": 4,
    }
    payload.update(overrides)
    return payload


def test_login_me_and_logout_round_trip(client: TestClient) -> None:
    login = client.post("/api/v1/auth/login", json={"username": " Admin ", "password": "test-admin-password"})
    assert login.status_code == 200, login.text
    assert login.json()["username"] == "admin"
    assert "booker_session" in login.cookies

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "admin"

    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_rejects_bad_credentials_without_leaking_which_field_failed(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong-password"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Usuario o contraseña incorrectos"


def test_protected_endpoints_require_a_session(client: TestClient) -> None:
    assert client.get("/api/v1/books").status_code == 401
    assert client.get("/api/v1/reports/daily-sales").status_code == 401


def test_health_checks_do_not_require_a_session(client: TestClient) -> None:
    assert client.get("/api/v1/health/live").json() == {"status": "ok"}
    assert client.get("/api/v1/health/ready").json() == {"status": "ready"}


def test_public_config_exposes_presentation_settings_only(client: TestClient) -> None:
    response = client.get("/api/v1/config/public")
    assert response.status_code == 200
    assert response.json() == {
        "currency": "EUR",
        "prices_include_tax": True,
        "low_stock_threshold": get_settings().low_stock_threshold,
    }
    assert "app_secret" not in response.text.lower()


def test_security_headers_are_present(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Request-ID"]


def test_catalog_crud_normalizes_isbn_and_strips_text(admin: TestClient) -> None:
    created = admin.post("/api/v1/books", json=book_payload(title="  El nombre del viento  ", isbn=" 978-0-306-40615-7 "))
    assert created.status_code == 201, created.text
    book = created.json()
    assert book["isbn"] == "9780306406157"
    assert book["title"] == "El nombre del viento"
    assert book["stock"] == 4

    found = admin.get("/api/v1/books/isbn/978-0-306-40615-7")
    assert found.status_code == 200
    assert found.json()["id"] == book["id"]

    updated = admin.patch(f"/api/v1/books/{book['id']}", json={"price": "13.95", "title": "  Nuevo título  "})
    assert updated.status_code == 200
    assert updated.json()["price"] == "13.95"
    assert updated.json()["title"] == "Nuevo título"


def test_catalog_rejects_invalid_and_duplicate_isbn(admin: TestClient) -> None:
    invalid = admin.post("/api/v1/books", json=book_payload(isbn="9780306406158"))
    assert invalid.status_code == 422

    assert admin.post("/api/v1/books", json=book_payload()).status_code == 201
    duplicate = admin.post("/api/v1/books", json=book_payload(title="Otro ejemplar"))
    assert duplicate.status_code == 409

    assert admin.get("/api/v1/books/isbn/not-an-isbn").status_code == 404


def test_catalog_rejects_blank_title_and_unknown_book(admin: TestClient) -> None:
    assert admin.post("/api/v1/books", json=book_payload(title="   ")).status_code == 422
    assert admin.get("/api/v1/books/00000000-0000-0000-0000-000000000000").status_code == 404
    assert admin.patch("/api/v1/books/00000000-0000-0000-0000-000000000000", json={"price": "1.00"}).status_code == 404


def test_catalog_search_treats_wildcards_literally_and_paginates(admin: TestClient) -> None:
    assert admin.post("/api/v1/books", json=book_payload(isbn=None, title="100% Real", authors="Ana")).status_code == 201
    assert admin.post("/api/v1/books", json=book_payload(isbn=None, title="Otra historia", authors="Luis")).status_code == 201

    literal = admin.get("/api/v1/books", params={"q": "100%"})
    assert literal.status_code == 200
    assert [item["title"] for item in literal.json()["items"]] == ["100% Real"]

    first_page = admin.get("/api/v1/books", params={"page": 1, "page_size": 1})
    second_page = admin.get("/api/v1/books", params={"page": 2, "page_size": 1})
    assert first_page.json()["total"] == 2
    assert len(first_page.json()["items"]) == 1
    assert first_page.json()["items"][0]["id"] != second_page.json()["items"][0]["id"]


def test_archived_books_leave_the_catalog_and_cannot_be_sold(admin: TestClient) -> None:
    book_id = admin.post("/api/v1/books", json=book_payload(isbn=None)).json()["id"]
    assert admin.delete(f"/api/v1/books/{book_id}").status_code == 204
    assert admin.get("/api/v1/books", params={"q": "El nombre del viento"}).json()["total"] == 0
    assert admin.get(f"/api/v1/books/{book_id}").json()["is_active"] is False

    response = admin.post("/api/v1/sales", json={
        "items": [{"book_id": book_id, "quantity": 1}],
        "payments": [{"method": "card", "amount": "12.50"}],
    }, headers={"Idempotency-Key": "archived-book"})
    assert response.status_code == 409


def test_catalog_permissions(admin: TestClient, supervisor: TestClient, cashier: TestClient) -> None:
    created = supervisor.post("/api/v1/books", json=book_payload(isbn=None))
    assert created.status_code == 201, created.text
    assert cashier.post("/api/v1/books", json=book_payload(isbn=None, title="No autorizado")).status_code == 403
    assert cashier.get("/api/v1/books").status_code == 200
    assert cashier.delete(f"/api/v1/books/{created.json()['id']}").status_code == 403


def test_admin_can_create_staff_but_cannot_remove_last_admin(admin: TestClient) -> None:
    created = admin.post("/api/v1/users", json={"username": " New.Cashier ", "password": "a-long-initial-password", "role": "cashier"})
    assert created.status_code == 201, created.text
    assert created.json()["username"] == "new.cashier"
    assert "password_hash" not in created.json()

    duplicate = admin.post("/api/v1/users", json={"username": "new.cashier", "password": "a-long-initial-password", "role": "cashier"})
    assert duplicate.status_code == 409

    last_admin = next(user for user in admin.get("/api/v1/users").json() if user["username"] == "admin")
    assert admin.patch(f"/api/v1/users/{last_admin['id']}", json={"is_active": False}).status_code == 409
    assert admin.patch(f"/api/v1/users/{last_admin['id']}", json={"role": "cashier"}).status_code == 409
    assert admin.patch(f"/api/v1/users/{last_admin['id']}", json={"is_active": None}).status_code == 422


def test_admin_can_rotate_password_and_deactivate_a_second_admin(admin: TestClient) -> None:
    second = admin.post("/api/v1/users", json={"username": "second-admin", "password": "a-long-initial-password", "role": "admin"}).json()
    assert admin.patch(f"/api/v1/users/{second['id']}", json={"password": "another-long-password"}).status_code == 200
    assert admin.patch(f"/api/v1/users/{second['id']}", json={"is_active": False}).status_code == 200

    with TestClient(admin.app) as other:
        assert other.post("/api/v1/auth/login", json={"username": "second-admin", "password": "another-long-password"}).status_code == 401


def test_only_administrators_manage_users(admin: TestClient, supervisor: TestClient) -> None:
    assert supervisor.get("/api/v1/users").status_code == 403
    assert supervisor.post("/api/v1/users", json={
        "username": "intruder", "password": "a-long-initial-password", "role": "cashier",
    }).status_code == 403
    assert admin.get("/api/v1/users").status_code == 200


def test_mutations_reject_untrusted_origin(admin: TestClient) -> None:
    response = admin.post("/api/v1/books", headers={"Origin": "https://attacker.example"}, json=book_payload())
    assert response.status_code == 403
    assert response.headers["X-Content-Type-Options"] == "nosniff"
