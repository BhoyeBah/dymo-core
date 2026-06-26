from datetime import datetime, date
from typing import Optional
import uuid
from pydantic import BaseModel, Field, model_validator, ConfigDict

class SaleCreate(BaseModel):
    amount: float = Field(..., gt=0, description="Total amount to pay")
    amount_received: float = Field(..., gt=0, description="Amount received from client")
    payment_method: str = Field(..., description="Payment method: cash, mobile_money, card, other")
    note: Optional[str] = Field(None, max_length=500)

    @model_validator(mode="after")
    def validate_payment_rules(self) -> 'SaleCreate':
        valid_methods = {"cash", "mobile_money", "card", "other"}
        if self.payment_method not in valid_methods:
            raise ValueError(f"Invalid payment method. Must be one of {valid_methods}")

        if self.payment_method == "cash":
            if self.amount_received < self.amount:
                raise ValueError("For cash payments, amount_received must be greater than or equal to amount")
        return self


class SaleCancelRequest(BaseModel):
    cancellation_reason: str = Field(..., min_length=3, max_length=500)


class SaleResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_by_user_id: uuid.UUID
    amount: float
    amount_received: float
    change_amount: float
    payment_method: str
    status: str
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    cancelled_at: Optional[datetime] = None
    cancelled_by_user_id: Optional[uuid.UUID] = None
    cancellation_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DayClosureCreate(BaseModel):
    closing_date: date
    real_cash_amount: float = Field(..., ge=0, description="Real cash counted in register")
    note: Optional[str] = Field(None, max_length=500)


class DayClosureResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    closed_by_user_id: uuid.UUID
    closing_date: date
    total_sales_amount: float
    total_sales_count: int
    cash_total: float
    mobile_money_total: float
    card_total: float
    expected_cash_amount: float
    real_cash_amount: float
    difference_amount: float
    note: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DailyReportResponse(BaseModel):
    date: date
    total_sales_amount: float
    total_sales_count: int
    cash_total: float
    mobile_money_total: float
    card_total: float
    other_total: float

    model_config = ConfigDict(from_attributes=True)
