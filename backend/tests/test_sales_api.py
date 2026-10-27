"""Checkout, payment, and return business rule integration tests."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def create_book(client: TestClient, stock: int = 3, isbn: str | None = None, price: str = "12.50") -> str:
    payload: dict[str, object] = {
        "title": "El nombre del viento",
        "authors": "Patrick Rothfuss",
        "price": price,
        "tax_rate": "0",
        "stock": stock,
    }
    if isbn is not None:
        payload["isbn"] = isbn
    response = client.post("/api/v1/books", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def sale_payload(book_id: str, quantity: int = 1, price: str = "12.50") -> dict[str, object]:
    total = float(price) * quantity
    return {
        "items": [{"book_id": book_id, "quantity": quantity}],
        "payments": [{"method": "cash", "amount": f"{total:.2f}", "cash_received": f"{total + 5:.2f}"}],
    }


def test_sale_is_atomic_idempotent_and_audited(admin: TestClient) -> None:
    book_id = create_book(admin)
    payload = sale_payload(book_id, 2)
    first = admin.post("/api/v1/sales", json=payload, headers={"Idempotency-Key": "checkout-001"})
    replay = admin.post("/api/v1/sales", json=payload, headers={"Idempotency-Key": "checkout-001"})

    assert first.status_code == 201, first.text
    assert replay.status_code == 201, replay.text
    assert first.json()["id"] == replay.json()["id"]
    assert first.json()["total"] == "25.00"
    assert first.json()["receipt_number"].startswith("BK-")
    assert admin.get("/api/v1/books/" + book_id).json()["stock"] == 1
    assert admin.get("/api/v1/sales").json()["total"] == 1


def test_missing_idempotency_key_is_rejected(admin: TestClient) -> None:
    book_id = create_book(admin)
    response = admin.post("/api/v1/sales", json=sale_payload(book_id))

    assert response.status_code == 400
    assert admin.get("/api/v1/books/" + book_id).json()["stock"] == 3


def test_insufficient_stock_does_not_create_a_sale(admin: TestClient) -> None:
    book_id = create_book(admin, stock=1)
    response = admin.post("/api/v1/sales", json=sale_payload(book_id, 2), headers={"Idempotency-Key": "checkout-stock"})

    assert response.status_code == 409
    assert admin.get("/api/v1/books/" + book_id).json()["stock"] == 1
    assert admin.get("/api/v1/sales").json()["items"] == []


def test_payment_total_mismatch_does_not_decrement_stock(admin: TestClient) -> None:
    book_id = create_book(admin, stock=2)
    response = admin.post("/api/v1/sales", json={
        "items": [{"book_id": book_id, "quantity": 1}],
        "payments": [{"method": "card", "amount": "10.00"}],
    }, headers={"Idempotency-Key": "payment-mismatch"})

    assert response.status_code == 422
    assert admin.get("/api/v1/books/" + book_id).json()["stock"] == 2
    assert admin.get("/api/v1/sales").json()["items"] == []


def test_cash_received_must_cover_cash_payment(admin: TestClient) -> None:
    book_id = create_book(admin)
    response = admin.post("/api/v1/sales", json={
        "items": [{"book_id": book_id, "quantity": 1}],
        "payments": [{"method": "cash", "amount": "12.50", "cash_received": "10.00"}],
    }, headers={"Idempotency-Key": "cash-short"})

    assert response.status_code == 422
    assert admin.get("/api/v1/books/" + book_id).json()["stock"] == 3


def test_split_cash_and_card_payment_is_recorded(admin: TestClient) -> None:
    book_id = create_book(admin)
    response = admin.post("/api/v1/sales", json={
        "items": [{"book_id": book_id, "quantity": 1}],
        "payments": [
            {"method": "cash", "amount": "5.00", "cash_received": "5.00"},
            {"method": "card", "amount": "7.50"},
        ],
    }, headers={"Idempotency-Key": "split-payment"})

    assert response.status_code == 201, response.text
    assert [payment["method"] for payment in response.json()["payments"]] == ["cash", "card"]
    assert response.json()["payments"][0]["change_given"] == "0.00"


def test_idempotency_key_cannot_be_reused_for_a_different_sale(admin: TestClient) -> None:
    book_id = create_book(admin, stock=3)
    admin.post("/api/v1/sales", json=sale_payload(book_id), headers={"Idempotency-Key": "checkout-reuse"})
    changed_request = admin.post("/api/v1/sales", json=sale_payload(book_id, 2), headers={"Idempotency-Key": "checkout-reuse"})

    assert changed_request.status_code == 409
    assert admin.get("/api/v1/books/" + book_id).json()["stock"] == 2


def test_concurrent_checkouts_cannot_sell_the_last_copy(admin: TestClient, postgres_only: None) -> None:
    del postgres_only
    book_id = create_book(admin, stock=1)
    barrier = Barrier(2)

    def checkout(key: str) -> int:
        with TestClient(app) as client:
            client.post("/api/v1/auth/login", json={"username": "admin", "password": "test-admin-password"})
            barrier.wait(timeout=5)
            response = client.post("/api/v1/sales", json=sale_payload(book_id), headers={"Idempotency-Key": key})
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(checkout, ["concurrent-1", "concurrent-2"]))

    assert sorted(results) == [201, 409]
    assert admin.get("/api/v1/books/" + book_id).json()["stock"] == 0
    assert admin.get("/api/v1/sales").json()["total"] == 1


def test_tax_inclusive_catalog_price_is_split_into_base_and_tax(admin: TestClient) -> None:
    book_id = admin.post("/api/v1/books", json={
        "title": "Precio con IVA",
        "price": "12.10",
        "tax_rate": "21.00",
        "stock": 1,
    }).json()["id"]
    response = admin.post("/api/v1/sales", json={
        "items": [{"book_id": book_id, "quantity": 1}],
        "payments": [{"method": "card", "amount": "12.10"}],
    }, headers={"Idempotency-Key": "tax-inclusive"})

    assert response.status_code == 201, response.text
    assert response.json()["subtotal"] == "10.00"
    assert response.json()["tax_total"] == "2.10"
    assert response.json()["total"] == "12.10"


def test_partial_return_rounding_preserves_the_original_line_total(admin: TestClient, supervisor: TestClient) -> None:
    settings = get_settings()
    previous_tax_mode = settings.prices_include_tax
    settings.prices_include_tax = False
    try:
        book_id = admin.post("/api/v1/books", json={"title": "Importe residual", "price": "0.01", "tax_rate": "21", "stock": 3}).json()["id"]
        sale = admin.post("/api/v1/sales", json={
            "items": [{"book_id": book_id, "quantity": 3}],
            "payments": [{"method": "card", "amount": "0.04"}],
        }, headers={"Idempotency-Key": "return-rounding"}).json()
        refunds = []

        for index in range(3):
            response = supervisor.post(f"/api/v1/sales/{sale['id']}/returns", json={
                "reason": f"Devolución parcial {index + 1}",
                "items": [{"sale_item_id": sale["items"][0]["id"], "quantity": 1, "restock": True}],
            })
            assert response.status_code == 201, response.text
            refunds.append(response.json()["refund_total"])

        assert refunds == ["0.01", "0.02", "0.01"]
    finally:
        settings.prices_include_tax = previous_tax_mode


def test_return_restocks_once_and_cannot_exceed_sold_quantity(admin: TestClient, supervisor: TestClient) -> None:
    book_id = create_book(admin, stock=2)
    sale = admin.post("/api/v1/sales", json=sale_payload(book_id), headers={"Idempotency-Key": "checkout-return"}).json()
    line_id = sale["items"][0]["id"]

    returned = supervisor.post(f"/api/v1/sales/{sale['id']}/returns", json={
        "reason": "Pedido por el cliente",
        "items": [{"sale_item_id": line_id, "quantity": 1, "restock": True}],
    })
    duplicate = supervisor.post(f"/api/v1/sales/{sale['id']}/returns", json={
        "reason": "Segundo intento",
        "items": [{"sale_item_id": line_id, "quantity": 1, "restock": True}],
    })

    assert returned.status_code == 201, returned.text
    assert returned.json()["refund_total"] == "12.50"
    assert duplicate.status_code == 409
    assert supervisor.get("/api/v1/books/" + book_id).json()["stock"] == 2


def test_return_without_restock_keeps_stock_unchanged(admin: TestClient, supervisor: TestClient) -> None:
    book_id = create_book(admin, stock=2)
    sale = admin.post("/api/v1/sales", json=sale_payload(book_id), headers={"Idempotency-Key": "return-no-restock"}).json()

    response = supervisor.post(f"/api/v1/sales/{sale['id']}/returns", json={
        "reason": "Copia dañada",
        "items": [{"sale_item_id": sale["items"][0]["id"], "quantity": 1, "restock": False}],
    })

    assert response.status_code == 201, response.text
    assert admin.get("/api/v1/books/" + book_id).json()["stock"] == 1


def test_cashier_can_sell_but_not_approve_returns(admin: TestClient, cashier: TestClient) -> None:
    book_id = create_book(admin, stock=2)
    sale = cashier.post("/api/v1/sales", json=sale_payload(book_id), headers={"Idempotency-Key": "cashier-sale"})
    assert sale.status_code == 201, sale.text
    denied = cashier.post(f"/api/v1/sales/{sale.json()['id']}/returns", json={
        "reason": "Intento de devolución",
        "items": [{"sale_item_id": sale.json()["items"][0]["id"], "quantity": 1, "restock": True}],
    })
    assert denied.status_code == 403
