"""Inventory and reporting API tests."""

from fastapi.testclient import TestClient


def create_book(client: TestClient, title: str, stock: int, price: str = "10.00") -> str:
    response = client.post("/api/v1/books", json={
        "title": title,
        "price": price,
        "tax_rate": "0",
        "stock": stock,
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_inventory_adjustment_updates_stock_and_records_reason(admin: TestClient, supervisor: TestClient) -> None:
    book_id = create_book(admin, "Inventario", 2)

    adjusted = supervisor.post("/api/v1/inventory/adjustments", json={
        "book_id": book_id,
        "quantity_delta": 3,
        "reason": "Recepción de proveedor",
    })
    assert adjusted.status_code == 201, adjusted.text
    assert adjusted.json()["quantity_delta"] == 3
    assert adjusted.json()["reason"] == "adjustment"
    assert adjusted.json()["notes"] == "Recepción de proveedor"
    assert supervisor.get(f"/api/v1/books/{book_id}").json()["stock"] == 5

    movements = supervisor.get("/api/v1/inventory/movements").json()
    assert any(movement["notes"] == "Recepción de proveedor" for movement in movements)


def test_inventory_rejects_zero_and_negative_stock(admin: TestClient, supervisor: TestClient) -> None:
    book_id = create_book(admin, "Inventario negativo", 1)

    zero = supervisor.post("/api/v1/inventory/adjustments", json={
        "book_id": book_id, "quantity_delta": 0, "reason": "Sin cambio",
    })
    assert zero.status_code == 422

    negative = supervisor.post("/api/v1/inventory/adjustments", json={
        "book_id": book_id, "quantity_delta": -2, "reason": "Recuento erróneo",
    })
    assert negative.status_code == 409
    assert admin.get(f"/api/v1/books/{book_id}").json()["stock"] == 1


def test_inventory_permissions(admin: TestClient, cashier: TestClient) -> None:
    book_id = create_book(admin, "Solo supervisores", 1)
    response = cashier.post("/api/v1/inventory/adjustments", json={
        "book_id": book_id, "quantity_delta": 1, "reason": "Intento no autorizado",
    })
    assert response.status_code == 403
    assert cashier.get("/api/v1/inventory/movements").status_code == 403


def test_low_stock_uses_configured_threshold(admin: TestClient) -> None:
    create_book(admin, "Casi agotado", 1)
    create_book(admin, "Disponible", 9)

    default_report = admin.get("/api/v1/reports/low-stock")
    assert default_report.status_code == 200
    assert [book["title"] for book in default_report.json()] == ["Casi agotado"]

    explicit = admin.get("/api/v1/reports/low-stock", params={"threshold": 10})
    assert len(explicit.json()) == 2

    none = admin.get("/api/v1/reports/low-stock", params={"threshold": 0})
    assert none.json() == []


def test_daily_report_subtracts_refunds_posted_that_day(admin: TestClient, supervisor: TestClient) -> None:
    book_id = create_book(admin, "Informe diario", 3, price="12.50")
    sale = admin.post("/api/v1/sales", json={
        "items": [{"book_id": book_id, "quantity": 2}],
        "payments": [{"method": "cash", "amount": "25.00", "cash_received": "30.00"}],
    }, headers={"Idempotency-Key": "daily-net"}).json()
    returned = supervisor.post(f"/api/v1/sales/{sale['id']}/returns", json={
        "reason": "Reembolso del día",
        "items": [{"sale_item_id": sale["items"][0]["id"], "quantity": 1, "restock": True}],
    })
    assert returned.status_code == 201
    detail = supervisor.get(f"/api/v1/sales/{sale['id']}").json()
    assert detail["status"] == "partially_returned"
    assert detail["items"][0]["returned_quantity"] == 1

    report = admin.get("/api/v1/reports/daily-sales")
    assert report.status_code == 200
    assert report.json()["date"]
    assert float(report.json()["sold_total"]) == 25.0
    assert float(report.json()["refunded_total"]) == 12.5
    assert float(report.json()["total"]) == 12.5
    assert report.json()["sale_count"] == 1
    assert report.json()["return_count"] == 1


def test_daily_sales_csv_export_contains_line_details(admin: TestClient) -> None:
    book_id = create_book(admin, "Libro; con punto y coma", 2, price="12.50")
    sale = admin.post("/api/v1/sales", json={
        "items": [{"book_id": book_id, "quantity": 2}],
        "payments": [{"method": "cash", "amount": "25.00", "cash_received": "25.00"}],
    }, headers={"Idempotency-Key": "csv-export"}).json()
    report_date = admin.get("/api/v1/reports/daily-sales").json()["date"]

    response = admin.get("/api/v1/reports/daily-sales.csv", params={"report_date": report_date})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert f'booker-ventas-{report_date}.csv' in response.headers["content-disposition"]
    text = response.content.decode("utf-8-sig")
    lines = text.splitlines()
    assert lines[0].split(";")[:4] == ["ticket", "fecha", "estado", "titulo"]
    assert sale["receipt_number"] in text
    assert "Libro; con punto y coma" in text
    assert "25.00" in text
    assert ";cash:25.00" in text


def test_reports_are_restricted_to_managers(admin: TestClient, cashier: TestClient) -> None:
    assert cashier.get("/api/v1/reports/daily-sales").status_code == 403
    assert cashier.get("/api/v1/reports/daily-sales.csv").status_code == 403
    assert cashier.get("/api/v1/reports/low-stock").status_code == 403
    assert admin.get("/api/v1/reports/daily-sales.csv").status_code == 200
