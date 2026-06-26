import uuid
from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Numeric, ForeignKey, DateTime, Date, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from dymo_saas_core.shared.base_model import BaseModel
from dymo_saas_core.shared.mixins import TenantMixin

class CashRegisterSale(BaseModel, TenantMixin):
    __tablename__ = "cash_register_sales"

    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_users.id", ondelete="SET NULL"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    amount_received: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    change_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)  # cash, mobile_money, card, other
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)  # completed, cancelled
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_users.id", ondelete="SET NULL"), nullable=True
    )
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        Index("ix_cash_register_sales_created_at", "created_at"),
        Index("ix_cash_register_sales_status", "status"),
    )


class CashRegisterDayClosure(BaseModel, TenantMixin):
    __tablename__ = "cash_register_day_closures"

    closed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_users.id", ondelete="SET NULL"), nullable=False
    )
    closing_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_sales_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    total_sales_count: Mapped[int] = mapped_column(nullable=False)
    cash_total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    mobile_money_total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    card_total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    expected_cash_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    real_cash_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    difference_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        Index("ix_cash_register_day_closures_created_at", "created_at"),
    )
