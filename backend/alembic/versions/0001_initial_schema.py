"""Create the initial Booker TPV schema."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table("users",
        sa.Column("id", UUID, primary_key=True), sa.Column("username", sa.String(80), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("role", sa.String(10), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_users_username", "users", ["username"])
    op.create_table("books",
        sa.Column("id", UUID, primary_key=True), sa.Column("isbn", sa.String(13), unique=True),
        sa.Column("title", sa.String(240), nullable=False), sa.Column("authors", sa.String(240), nullable=False),
        sa.Column("publisher", sa.String(160)), sa.Column("category", sa.String(100)),
        sa.Column("price", sa.Numeric(12, 2), nullable=False), sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_books_price_nonnegative"),
        sa.CheckConstraint("stock >= 0", name="ck_books_stock_nonnegative"))
    op.create_index("ix_books_isbn", "books", ["isbn"])
    op.create_index("ix_books_title", "books", ["title"])
    op.create_table("sales",
        sa.Column("id", UUID, primary_key=True), sa.Column("receipt_number", sa.String(32), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_total", sa.Numeric(12, 2), nullable=False), sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False), sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.UniqueConstraint("created_by", "idempotency_key", name="uq_sale_idempotency"),
        sa.CheckConstraint("total >= 0", name="ck_sales_total_nonnegative"))
    op.create_index("ix_sales_receipt_number", "sales", ["receipt_number"])
    op.create_table("sale_items",
        sa.Column("id", UUID, primary_key=True), sa.Column("sale_id", UUID, sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("book_id", UUID, sa.ForeignKey("books.id", ondelete="SET NULL")), sa.Column("isbn_snapshot", sa.String(13)),
        sa.Column("title_snapshot", sa.String(240), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False), sa.Column("tax_rate_snapshot", sa.Numeric(5, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False), sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_sale_items_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0 AND line_total >= 0", name="ck_sale_items_amounts_nonnegative"))
    op.create_index("ix_sale_items_sale_id", "sale_items", ["sale_id"])
    op.create_table("payments",
        sa.Column("id", UUID, primary_key=True), sa.Column("sale_id", UUID, sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("method", sa.String(5), nullable=False), sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("cash_received", sa.Numeric(12, 2)), sa.Column("change_given", sa.Numeric(12, 2)), sa.Column("external_reference", sa.String(120)),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount_positive"))
    op.create_index("ix_payments_sale_id", "payments", ["sale_id"])
    op.create_table("stock_movements",
        sa.Column("id", UUID, primary_key=True), sa.Column("book_id", UUID, sa.ForeignKey("books.id"), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False), sa.Column("reason", sa.String(40), nullable=False),
        sa.Column("reference_id", UUID), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id"), nullable=False), sa.Column("notes", sa.Text()))
    op.create_index("ix_stock_movements_book_id", "stock_movements", ["book_id"])
    op.create_index("ix_stock_movements_reference_id", "stock_movements", ["reference_id"])
    op.create_table("returns",
        sa.Column("id", UUID, primary_key=True), sa.Column("sale_id", UUID, sa.ForeignKey("sales.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("created_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False), sa.Column("refund_total", sa.Numeric(12, 2), nullable=False))
    op.create_index("ix_returns_sale_id", "returns", ["sale_id"])
    op.create_table("return_items",
        sa.Column("id", UUID, primary_key=True), sa.Column("return_id", UUID, sa.ForeignKey("returns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sale_item_id", UUID, sa.ForeignKey("sale_items.id"), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_refund", sa.Numeric(12, 2), nullable=False), sa.Column("restock", sa.Boolean(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_return_items_quantity_positive"))
    op.create_index("ix_return_items_return_id", "return_items", ["return_id"])
    op.create_index("ix_return_items_sale_item_id", "return_items", ["sale_item_id"])
    op.create_table("audit_events",
        sa.Column("id", UUID, primary_key=True), sa.Column("actor_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(80), nullable=False), sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", UUID, nullable=False), sa.Column("reason", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_index("ix_return_items_sale_item_id", table_name="return_items")
    op.drop_index("ix_return_items_return_id", table_name="return_items")
    op.drop_table("return_items")
    op.drop_index("ix_returns_sale_id", table_name="returns")
    op.drop_table("returns")
    op.drop_index("ix_stock_movements_reference_id", table_name="stock_movements")
    op.drop_index("ix_stock_movements_book_id", table_name="stock_movements")
    op.drop_table("stock_movements")
    op.drop_index("ix_payments_sale_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_sale_items_sale_id", table_name="sale_items")
    op.drop_table("sale_items")
    op.drop_index("ix_sales_receipt_number", table_name="sales")
    op.drop_table("sales")
    op.drop_index("ix_books_title", table_name="books")
    op.drop_index("ix_books_isbn", table_name="books")
    op.drop_table("books")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")