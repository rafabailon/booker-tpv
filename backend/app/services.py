"""Transactional business rules for checkout, returns and stock."""

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models import (
    AuditEvent,
    Book,
    Payment,
    PaymentMethod,
    Return,
    ReturnItem,
    Sale,
    SaleItem,
    SaleStatus,
    StockMovement,
    User,
)
from app.schemas import InventoryAdjustment, ReturnCreate, SaleCreate

CENT = Decimal("0.01")
RECEIPT_PREFIX = "BK"


def money(value: Decimal) -> Decimal:
    """Round currency amounts using conventional half-up rounding."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _fingerprint(payload: SaleCreate) -> str:
    """Hash a normalized request body for idempotency conflict detection."""
    serialized = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def _sale_query(sale_id: UUID):
    return select(Sale).where(Sale.id == sale_id).options(selectinload(Sale.items), selectinload(Sale.payments))


def _existing_idempotent_sale(db: Session, user_id: UUID, key: str, fingerprint: str) -> Sale | None:
    sale = db.scalar(
        select(Sale).where(Sale.created_by == user_id, Sale.idempotency_key == key).options(
            selectinload(Sale.items), selectinload(Sale.payments)
        )
    )
    if sale is not None and sale.request_fingerprint != fingerprint:
        raise HTTPException(status_code=409, detail="La clave de idempotencia ya se usó con otra venta")
    return sale


def create_sale(db: Session, user: User, key: str, payload: SaleCreate) -> Sale:
    """Create a complete sale and decrement stock atomically."""
    if not key or len(key) > 100:
        raise HTTPException(status_code=400, detail="La cabecera Idempotency-Key es obligatoria (máximo 100 caracteres)")
    fingerprint = _fingerprint(payload)
    existing = _existing_idempotent_sale(db, user.id, key, fingerprint)
    if existing is not None:
        return existing
    db.rollback()

    quantities: dict[UUID, int] = defaultdict(int)
    for item in payload.items:
        quantities[item.book_id] += item.quantity

    try:
        with db.begin():
            books = db.scalars(
                select(Book).where(Book.id.in_(quantities)).order_by(Book.id).with_for_update()
            ).all()
            book_by_id = {book.id: book for book in books}
            if len(book_by_id) != len(quantities):
                raise HTTPException(status_code=404, detail="Uno o más libros ya no existen")

            for book_id, quantity in quantities.items():
                book = book_by_id[book_id]
                if not book.is_active:
                    raise HTTPException(status_code=409, detail=f"El libro '{book.title}' no está disponible")
                if book.stock < quantity:
                    raise HTTPException(status_code=409, detail=f"Stock insuficiente para '{book.title}'")

            settings = get_settings()
            total = Decimal("0.00")
            tax_total = Decimal("0.00")
            subtotal = Decimal("0.00")
            sale_items: list[SaleItem] = []
            for book_id, quantity in quantities.items():
                book = book_by_id[book_id]
                base_total = money(book.price * quantity)
                if book.tax_rate and settings.prices_include_tax:
                    tax_amount = money(base_total * book.tax_rate / (Decimal("100") + book.tax_rate))
                    line_total = base_total
                elif book.tax_rate:
                    tax_amount = money(base_total * book.tax_rate / Decimal("100"))
                    line_total = money(base_total + tax_amount)
                else:
                    tax_amount = Decimal("0.00")
                    line_total = base_total
                subtotal += line_total - tax_amount if settings.prices_include_tax else base_total
                total += line_total
                tax_total += tax_amount
                sale_items.append(SaleItem(
                    book_id=book.id,
                    isbn_snapshot=book.isbn,
                    title_snapshot=book.title,
                    quantity=quantity,
                    unit_price=book.price,
                    tax_rate_snapshot=book.tax_rate,
                    tax_amount=tax_amount,
                    line_total=line_total,
                ))
            total = money(total)
            tax_total = money(tax_total)
            if money(sum((payment.amount for payment in payload.payments), Decimal("0"))) != total:
                raise HTTPException(status_code=422, detail="Los importes de pago deben sumar el total de la venta")
            for payment in payload.payments:
                if payment.method == PaymentMethod.CASH:
                    if payment.cash_received is None or payment.cash_received < payment.amount:
                        raise HTTPException(status_code=422, detail="El efectivo recibido debe cubrir el importe en efectivo")
                elif payment.cash_received is not None:
                    raise HTTPException(status_code=422, detail="Solo el pago en efectivo admite efectivo recibido")

            sale_id = uuid4()
            sale = Sale(
                id=sale_id,
                receipt_number=f"{RECEIPT_PREFIX}-{datetime.now(timezone.utc):%Y%m%d}-{sale_id.hex[:8].upper()}",
                created_by=user.id,
                subtotal=money(subtotal),
                tax_total=tax_total,
                total=total,
                currency=settings.app_currency,
                idempotency_key=key,
                request_fingerprint=fingerprint,
                items=sale_items,
                payments=[Payment(
                    method=payment.method,
                    amount=payment.amount,
                    cash_received=payment.cash_received,
                    change_given=money(payment.cash_received - payment.amount) if payment.cash_received is not None else None,
                    external_reference=payment.external_reference,
                ) for payment in payload.payments],
            )
            db.add(sale)
            for book_id, quantity in quantities.items():
                book = book_by_id[book_id]
                book.stock -= quantity
                db.add(StockMovement(book_id=book_id, quantity_delta=-quantity, reason="sale", reference_id=sale_id, created_by=user.id))
            db.add(AuditEvent(actor_id=user.id, action="sale.created", entity_type="sale", entity_id=sale_id))
            db.flush()
        return db.scalar(_sale_query(sale_id))  # type: ignore[return-value]
    except IntegrityError:
        db.rollback()
        existing = _existing_idempotent_sale(db, user.id, key, fingerprint)
        if existing is not None:
            return existing
        raise


def create_return(db: Session, user: User, sale_id: UUID, payload: ReturnCreate) -> Return:
    """Return sale lines without allowing over-refunds or duplicate stock."""
    db.rollback()
    with db.begin():
        sale = db.scalar(select(Sale).where(Sale.id == sale_id).with_for_update())
        if sale is None:
            raise HTTPException(status_code=404, detail="Venta no encontrada")
        lines = db.scalars(select(SaleItem).where(SaleItem.sale_id == sale_id).with_for_update()).all()
        line_by_id = {line.id: line for line in lines}
        prior_returns = db.execute(
            select(ReturnItem.sale_item_id, func.sum(ReturnItem.quantity))
            .join(Return, Return.id == ReturnItem.return_id)
            .where(Return.sale_id == sale_id)
            .group_by(ReturnItem.sale_item_id)
        ).all()
        already_returned = {line_id: quantity for line_id, quantity in prior_returns}
        requested: dict[UUID, int] = defaultdict(int)
        restock_by_line: dict[UUID, bool] = {}
        for item in payload.items:
            requested[item.sale_item_id] += item.quantity
            restock_by_line[item.sale_item_id] = restock_by_line.get(item.sale_item_id, False) or item.restock
        for line_id, quantity in requested.items():
            line = line_by_id.get(line_id)
            if line is None or quantity + already_returned.get(line_id, 0) > line.quantity:
                raise HTTPException(status_code=409, detail="La devolución supera las unidades disponibles de la venta")

        return_id = uuid4()
        refund_amounts: dict[UUID, Decimal] = {}
        for line_id, quantity in requested.items():
            line = line_by_id[line_id]
            previously_returned = already_returned.get(line_id, 0)
            previously_refunded = money(line.line_total * previously_returned / line.quantity)
            cumulatively_refunded = money(line.line_total * (previously_returned + quantity) / line.quantity)
            refund_amounts[line_id] = cumulatively_refunded - previously_refunded
        refund_total = money(sum(refund_amounts.values(), Decimal("0")))
        return_record = Return(
            id=return_id,
            sale_id=sale_id,
            created_by=user.id,
            reason=payload.reason,
            refund_total=refund_total,
        )
        db.add(return_record)
        db.flush()
        for line_id, quantity in requested.items():
            line = line_by_id[line_id]
            db.add(ReturnItem(
                return_id=return_id,
                sale_item_id=line_id,
                quantity=quantity,
                unit_refund=money(refund_amounts[line_id] / quantity),
                restock=restock_by_line[line_id],
            ))
            if restock_by_line[line_id] and line.book_id is not None:
                book = db.scalar(select(Book).where(Book.id == line.book_id).with_for_update())
                if book is not None:
                    book.stock += quantity
                    db.add(StockMovement(book_id=book.id, quantity_delta=quantity, reason="return", reference_id=return_id, created_by=user.id, notes=payload.reason))
        total_returned = sum(already_returned.values()) + sum(requested.values())
        sale.status = SaleStatus.RETURNED if total_returned == sum(line.quantity for line in lines) else SaleStatus.PARTIALLY_RETURNED
        db.add(AuditEvent(actor_id=user.id, action="sale.returned", entity_type="return", entity_id=return_id, reason=payload.reason))
    db.refresh(return_record)
    return return_record


def adjust_inventory(db: Session, user: User, payload: InventoryAdjustment) -> StockMovement:
    """Apply a supervised stock adjustment with a mandatory reason."""
    if payload.quantity_delta == 0:
        raise HTTPException(status_code=422, detail="El ajuste de stock no puede ser cero")
    db.rollback()
    with db.begin():
        book = db.scalar(select(Book).where(Book.id == payload.book_id).with_for_update())
        if book is None:
            raise HTTPException(status_code=404, detail="Libro no encontrado")
        if book.stock + payload.quantity_delta < 0:
            raise HTTPException(status_code=409, detail="El ajuste dejaría el stock por debajo de cero")
        book.stock += payload.quantity_delta
        movement = StockMovement(book_id=book.id, quantity_delta=payload.quantity_delta, reason="adjustment", created_by=user.id, notes=payload.reason)
        db.add(movement)
        db.add(AuditEvent(actor_id=user.id, action="inventory.adjusted", entity_type="book", entity_id=book.id, reason=payload.reason))
        db.flush()
    db.refresh(movement)
    return movement