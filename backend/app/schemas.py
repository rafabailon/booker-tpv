"""Typed request and response models for the HTTP API."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.isbn import normalize_isbn
from app.models import PaymentMethod, SaleStatus, UserRole

Money = Annotated[Decimal, Field(max_digits=12, decimal_places=2, ge=0)]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("username", mode="before")
    @classmethod
    def strip_username(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class UserRead(BaseModel):
    id: UUID
    username: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    role: UserRole

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class UserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=256)

    @field_validator("role", "is_active", "password")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("El valor no puede ser nulo")
        return value


class UserAdminRead(UserRead):
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookCreate(BaseModel):
    isbn: str | None = None
    title: str = Field(min_length=1, max_length=240)
    authors: str = Field(default="", max_length=240)
    publisher: str | None = Field(default=None, max_length=160)
    category: str | None = Field(default=None, max_length=100)
    price: Money
    tax_rate: Annotated[Decimal, Field(max_digits=5, decimal_places=2, ge=0, le=100)] = Decimal("0")
    stock: int = Field(default=0, ge=0)

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, value: str | None) -> str | None:
        return normalize_isbn(value)

    @field_validator("title", "authors", "publisher", "category", mode="before")
    @classmethod
    def strip_catalog_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class BookUpdate(BaseModel):
    isbn: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=240)
    authors: str | None = Field(default=None, max_length=240)
    publisher: str | None = Field(default=None, max_length=160)
    category: str | None = Field(default=None, max_length=100)
    price: Money | None = None
    tax_rate: Annotated[Decimal, Field(max_digits=5, decimal_places=2, ge=0, le=100)] | None = None

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, value: str | None) -> str | None:
        return normalize_isbn(value)

    @field_validator("title", "authors", "publisher", "category", mode="before")
    @classmethod
    def strip_catalog_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("title", "authors", "price", "tax_rate")
    @classmethod
    def reject_null_for_required_fields(cls, value: object) -> object:
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class BookRead(BookCreate):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PageBooks(BaseModel):
    items: list[BookRead]
    page: int
    page_size: int
    total: int


class SaleLineRequest(BaseModel):
    book_id: UUID
    quantity: int = Field(gt=0, le=1000)


class PaymentRequest(BaseModel):
    method: PaymentMethod
    amount: Annotated[Decimal, Field(max_digits=12, decimal_places=2, gt=0)]
    cash_received: Annotated[Decimal, Field(max_digits=12, decimal_places=2, ge=0)] | None = None
    external_reference: str | None = Field(default=None, max_length=120)

    @field_validator("external_reference", mode="before")
    @classmethod
    def strip_reference(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class SaleCreate(BaseModel):
    items: list[SaleLineRequest] = Field(min_length=1, max_length=100)
    payments: list[PaymentRequest] = Field(min_length=1, max_length=5)


class SaleItemRead(BaseModel):
    id: UUID
    book_id: UUID | None
    isbn_snapshot: str | None
    title_snapshot: str
    quantity: int
    unit_price: Decimal
    tax_rate_snapshot: Decimal
    tax_amount: Decimal
    line_total: Decimal
    returned_quantity: int = 0

    model_config = ConfigDict(from_attributes=True)


class PaymentRead(BaseModel):
    method: PaymentMethod
    amount: Decimal
    cash_received: Decimal | None
    change_given: Decimal | None

    model_config = ConfigDict(from_attributes=True)


class SaleRead(BaseModel):
    id: UUID
    receipt_number: str
    created_at: datetime
    status: SaleStatus
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    currency: str
    items: list[SaleItemRead]
    payments: list[PaymentRead]

    model_config = ConfigDict(from_attributes=True)


class PageSales(BaseModel):
    items: list[SaleRead]
    page: int
    page_size: int
    total: int


class DailySalesReport(BaseModel):
    date: str
    total: Decimal
    sold_total: Decimal
    refunded_total: Decimal
    currency: str
    sale_count: int
    return_count: int


class ReturnLineRequest(BaseModel):
    sale_item_id: UUID
    quantity: int = Field(gt=0)
    restock: bool = True


class ReturnCreate(BaseModel):
    reason: str = Field(min_length=2, max_length=500)
    items: list[ReturnLineRequest] = Field(min_length=1, max_length=100)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_reason(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ReturnRead(BaseModel):
    id: UUID
    sale_id: UUID
    created_at: datetime
    reason: str
    refund_total: Decimal

    model_config = ConfigDict(from_attributes=True)


class InventoryAdjustment(BaseModel):
    book_id: UUID
    quantity_delta: int
    reason: str = Field(min_length=3, max_length=500)


class InventoryMovementRead(BaseModel):
    id: UUID
    book_id: UUID
    quantity_delta: int
    reason: str
    reference_id: UUID | None
    created_at: datetime
    created_by: UUID
    notes: str | None

    model_config = ConfigDict(from_attributes=True)