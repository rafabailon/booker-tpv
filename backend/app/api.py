"""Versioned Booker TPV HTTP endpoints."""

import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import get_db
from app.dependencies import administrator, catalog_manager, staff_user, supervisor
from app.isbn import normalize_isbn
from app.models import AuditEvent, Book, Return, ReturnItem, Sale, StockMovement, User, UserRole
from app.schemas import (
    BookCreate,
    BookRead,
    BookUpdate,
    DailySalesReport,
    InventoryAdjustment,
    InventoryMovementRead,
    LoginRequest,
    PageBooks,
    PageSales,
    ReturnCreate,
    ReturnRead,
    SaleCreate,
    SaleRead,
    UserRead,
    UserAdminRead,
    UserCreate,
    UserUpdate,
)
from app.security import hash_password, verify_password
from app.services import adjust_inventory, create_return, create_sale

router = APIRouter(prefix="/api/v1")
DbSession = Annotated[Session, Depends(get_db)]
Staff = Annotated[User, Depends(staff_user)]
CatalogManager = Annotated[User, Depends(catalog_manager)]
Supervisor = Annotated[User, Depends(supervisor)]
Administrator = Annotated[User, Depends(administrator)]


def _escape_like(term: str) -> str:
    """Escape user input so SQL wildcards remain literal characters."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _isbn_filter(value: str) -> str:
    """Normalize an ISBN search value or return a client-facing validation error."""
    try:
        normalized = normalize_isbn(value)
    except ValueError:
        raise HTTPException(status_code=422, detail="El ISBN no es válido") from None
    return normalized or ""


def _day_bounds(target: date) -> tuple[datetime, datetime]:
    """Translate a store-local calendar day into UTC boundaries."""
    local_zone = ZoneInfo(get_settings().app_timezone)
    start = datetime.combine(target, time.min, tzinfo=local_zone).astimezone(timezone.utc)
    end = (datetime.combine(target, time.min, tzinfo=local_zone) + timedelta(days=1)).astimezone(timezone.utc)
    return start, end


@router.get("/config/public")
def public_config() -> dict[str, str | bool | int]:
    """Expose non-secret presentation settings used to display store prices."""
    settings = get_settings()
    return {
        "currency": settings.app_currency,
        "prices_include_tax": settings.prices_include_tax,
        "low_stock_threshold": settings.low_stock_threshold,
    }


@router.post("/auth/login", response_model=UserRead)
def login(payload: LoginRequest, request: Request, db: DbSession) -> User:
    """Authenticate a user and issue a signed HTTP-only session cookie."""
    user = db.scalar(select(User).where(func.lower(User.username) == payload.username.lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    request.session.clear()
    request.session["user_id"] = str(user.id)
    return user


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, _: Staff) -> Response:
    """Clear the current user's session."""
    request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/me", response_model=UserRead)
def me(user: Staff) -> User:
    """Return the authenticated user profile."""
    return user


@router.get("/users", response_model=list[UserAdminRead])
def list_users(db: DbSession, _: Administrator) -> list[User]:
    """List user accounts without exposing password hashes."""
    return list(db.scalars(select(User).order_by(User.username)).all())


@router.post("/users", response_model=UserAdminRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DbSession, actor: Administrator) -> User:
    """Create a staff account with a hashed password."""
    user = User(username=payload.username, password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    try:
        db.flush()
        db.add(AuditEvent(actor_id=actor.id, action="user.created", entity_type="user", entity_id=user.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese nombre") from None
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserAdminRead)
def update_user(user_id: UUID, payload: UserUpdate, db: DbSession, actor: Administrator) -> User:
    """Change account role/status or rotate its password."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    changes = payload.model_dump(exclude_unset=True)
    if user.id == actor.id and changes.get("is_active") is False:
        raise HTTPException(status_code=409, detail="No puedes desactivar tu propia cuenta")
    if user.role == UserRole.ADMIN and user.is_active and (changes.get("role") not in (None, UserRole.ADMIN) or changes.get("is_active") is False):
        active_admins = db.scalar(select(func.count()).select_from(User).where(User.role == UserRole.ADMIN, User.is_active.is_(True))) or 0
        if active_admins <= 1:
            raise HTTPException(status_code=409, detail="No puedes desactivar o cambiar el rol del último administrador activo")
    if "password" in changes:
        user.password_hash = hash_password(changes.pop("password"))
    for field, value in changes.items():
        setattr(user, field, value)
    db.add(AuditEvent(actor_id=actor.id, action="user.updated", entity_type="user", entity_id=user.id))
    db.commit()
    db.refresh(user)
    return user


@router.get("/books", response_model=PageBooks)
def list_books(
    db: DbSession,
    _: Staff,
    q: str | None = Query(default=None, max_length=240),
    isbn: str | None = Query(default=None, max_length=20),
    active: bool = True,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
) -> PageBooks:
    """Search the active catalog with bounded pagination."""
    query = select(Book).where(Book.is_active == active)
    if q:
        term = f"%{_escape_like(q.strip())}%"
        query = query.where(or_(
            Book.title.ilike(term, escape="\\"),
            Book.authors.ilike(term, escape="\\"),
            Book.isbn.ilike(term, escape="\\"),
        ))
    if isbn:
        query = query.where(Book.isbn == _isbn_filter(isbn))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(Book.title, Book.id).offset((page - 1) * page_size).limit(page_size)).all()
    return PageBooks(items=items, page=page, page_size=page_size, total=total)


@router.post("/books", response_model=BookRead, status_code=status.HTTP_201_CREATED)
def create_book(payload: BookCreate, db: DbSession, user: CatalogManager) -> Book:
    """Create a catalog entry and audit the change."""
    book = Book(**payload.model_dump())
    db.add(book)
    try:
        db.flush()
        db.add(AuditEvent(actor_id=user.id, action="book.created", entity_type="book", entity_id=book.id))
        if book.stock:
            db.add(StockMovement(book_id=book.id, quantity_delta=book.stock, reason="initial", created_by=user.id, notes="Stock inicial"))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un libro con ese ISBN") from None
    db.refresh(book)
    return book


@router.get("/books/isbn/{isbn}", response_model=BookRead)
def find_book_by_isbn(isbn: str, db: DbSession, _: Staff) -> Book:
    """Find one active book by its normalized ISBN."""
    try:
        normalized = normalize_isbn(isbn)
    except ValueError:
        raise HTTPException(status_code=404, detail="Libro no encontrado") from None
    if not normalized:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    book = db.scalar(select(Book).where(Book.isbn == normalized, Book.is_active.is_(True)))
    if book is None:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return book


@router.get("/books/{book_id}", response_model=BookRead)
def get_book(book_id: UUID, db: DbSession, _: Staff) -> Book:
    """Read a catalog entry by identifier."""
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return book


@router.patch("/books/{book_id}", response_model=BookRead)
def update_book(book_id: UUID, payload: BookUpdate, db: DbSession, user: CatalogManager) -> Book:
    """Update catalog fields while retaining historical sale snapshots."""
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(book, field, value)
    try:
        db.add(AuditEvent(actor_id=user.id, action="book.updated", entity_type="book", entity_id=book.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ya existe un libro con ese ISBN") from None
    db.refresh(book)
    return book


@router.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_book(book_id: UUID, db: DbSession, user: CatalogManager) -> Response:
    """Archive a book rather than deleting sales history."""
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    book.is_active = False
    db.add(AuditEvent(actor_id=user.id, action="book.archived", entity_type="book", entity_id=book.id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sales", response_model=SaleRead, status_code=status.HTTP_201_CREATED)
def checkout(
    payload: SaleCreate,
    db: DbSession,
    user: Staff,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Sale:
    """Create or replay an idempotent checkout."""
    if idempotency_key is None:
        raise HTTPException(status_code=400, detail="Falta la cabecera Idempotency-Key")
    return create_sale(db, user, idempotency_key, payload)


@router.get("/sales", response_model=PageSales)
def list_sales(
    db: DbSession,
    _: Staff,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
) -> PageSales:
    """List sales in reverse chronological order with bounded pagination."""
    query = select(Sale).options(selectinload(Sale.items), selectinload(Sale.payments))
    total = db.scalar(select(func.count()).select_from(Sale)) or 0
    items = list(db.scalars(
        query.order_by(Sale.created_at.desc(), Sale.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all())
    return PageSales(items=items, page=page, page_size=page_size, total=total)


@router.get("/sales/{sale_id}", response_model=SaleRead)
def get_sale(sale_id: UUID, db: DbSession, _: Staff) -> SaleRead:
    """Read a sale and its immutable line/payment snapshots."""
    sale = db.scalar(select(Sale).where(Sale.id == sale_id).options(selectinload(Sale.items), selectinload(Sale.payments)))
    if sale is None:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    returned_rows = db.execute(
        select(ReturnItem.sale_item_id, func.sum(ReturnItem.quantity))
        .join(Return, Return.id == ReturnItem.return_id)
        .where(Return.sale_id == sale_id)
        .group_by(ReturnItem.sale_item_id)
    ).all()
    returned_by_item = {item_id: quantity for item_id, quantity in returned_rows}
    response = SaleRead.model_validate(sale)
    return response.model_copy(update={
        "items": [
            item.model_copy(update={"returned_quantity": returned_by_item.get(item.id, 0)})
            for item in response.items
        ]
    })


@router.post("/sales/{sale_id}/returns", response_model=ReturnRead, status_code=status.HTTP_201_CREATED)
def return_sale(sale_id: UUID, payload: ReturnCreate, db: DbSession, user: Supervisor) -> ReturnRead:
    """Return sold items; only supervisors and administrators may approve."""
    result = create_return(db, user, sale_id, payload)
    return ReturnRead.model_validate(result)


@router.post("/inventory/adjustments", response_model=InventoryMovementRead, status_code=status.HTTP_201_CREATED)
def inventory_adjustment(payload: InventoryAdjustment, db: DbSession, user: Supervisor) -> StockMovement:
    """Adjust inventory with a mandatory explanation."""
    return adjust_inventory(db, user, payload)


@router.get("/inventory/movements", response_model=list[InventoryMovementRead])
def inventory_movements(
    db: DbSession,
    _: CatalogManager,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> list[StockMovement]:
    """List recent stock movements."""
    query = select(StockMovement).order_by(StockMovement.created_at.desc())
    return list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all())


@router.get("/reports/daily-sales", response_model=DailySalesReport)
def daily_sales(db: DbSession, _: CatalogManager, report_date: date | None = None) -> DailySalesReport:
    """Report gross sales, refunds, and net totals for the configured store's local day."""
    settings = get_settings()
    local_date = report_date or datetime.now(ZoneInfo(settings.app_timezone)).date()
    start, end = _day_bounds(local_date)
    sold_total, sale_count = db.execute(
        select(func.coalesce(func.sum(Sale.total), Decimal("0.00")), func.count(Sale.id))
        .where(Sale.created_at >= start, Sale.created_at < end)
    ).one()
    refunded_total, return_count = db.execute(
        select(func.coalesce(func.sum(Return.refund_total), Decimal("0.00")), func.count(Return.id))
        .where(Return.created_at >= start, Return.created_at < end)
    ).one()
    normalized_sold = sold_total or Decimal("0.00")
    normalized_refunded = refunded_total or Decimal("0.00")
    return DailySalesReport(
        date=local_date.isoformat(),
        total=normalized_sold - normalized_refunded,
        sold_total=normalized_sold,
        refunded_total=normalized_refunded,
        currency=settings.app_currency,
        sale_count=sale_count,
        return_count=return_count,
    )


@router.get("/reports/daily-sales.csv")
def daily_sales_csv(db: DbSession, _: CatalogManager, report_date: date | None = None) -> Response:
    """Export the sale lines of one local day as a spreadsheet-friendly CSV."""
    settings = get_settings()
    local_date = report_date or datetime.now(ZoneInfo(settings.app_timezone)).date()
    start, end = _day_bounds(local_date)
    sales = db.scalars(
        select(Sale)
        .where(Sale.created_at >= start, Sale.created_at < end)
        .options(selectinload(Sale.items), selectinload(Sale.payments))
        .order_by(Sale.created_at, Sale.id)
    ).all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")
    writer.writerow([
        "ticket",
        "fecha",
        "estado",
        "titulo",
        "isbn",
        "cantidad",
        "precio_unitario",
        "iva",
        "importe",
        "moneda",
        "pagos",
    ])
    for sale in sales:
        payments = " | ".join(f"{payment.method.value}:{payment.amount:.2f}" for payment in sale.payments)
        for item in sale.items:
            writer.writerow([
                sale.receipt_number,
                sale.created_at.isoformat(),
                sale.status.value,
                item.title_snapshot,
                item.isbn_snapshot or "",
                item.quantity,
                f"{item.unit_price:.2f}",
                f"{item.tax_rate_snapshot:.2f}",
                f"{item.line_total:.2f}",
                sale.currency,
                payments,
            ])

    filename = f"booker-ventas-{local_date.isoformat()}.csv"
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/low-stock", response_model=list[BookRead])
def low_stock(db: DbSession, _: CatalogManager, threshold: int | None = Query(default=None, ge=0, le=10000)) -> list[Book]:
    """List active books at or below the configured low-stock threshold."""
    limit = get_settings().low_stock_threshold if threshold is None else threshold
    query = (
        select(Book)
        .where(Book.is_active.is_(True), Book.stock <= limit)
        .order_by(Book.stock, Book.title)
        .limit(200)
    )
    return list(db.scalars(query).all())


@router.get("/health/live")
def live() -> dict[str, str]:
    """Indicate that the API process is responding."""
    return {"status": "ok"}


@router.get("/health/ready")
def ready(db: DbSession) -> dict[str, str]:
    """Check required database connectivity."""
    db.execute(select(1))
    return {"status": "ready"}