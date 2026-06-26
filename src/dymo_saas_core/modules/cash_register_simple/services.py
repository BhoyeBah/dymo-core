import uuid
from datetime import datetime, date, timezone, timedelta
from typing import List, Optional
from sqlalchemy import func, Date, and_
from sqlalchemy.orm import Session

from dymo_saas_core.core.exceptions import NotFoundException
from dymo_saas_core.core.quota import check_limit, increment_usage
from dymo_saas_core.core.outbox import emit_event
from dymo_saas_core.core.utils import write_audit_log
from dymo_saas_core.modules.cash_register_simple.models import CashRegisterSale, CashRegisterDayClosure
from dymo_saas_core.modules.cash_register_simple.schemas import SaleCreate, DayClosureCreate

def create_sale(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, sale_in: SaleCreate) -> CashRegisterSale:
    # 1. Enforce quota gating
    check_limit(db, tenant_id, "cash_register_simple.sales.monthly", requested_amount=1)

    # 2. Calculate change amount based on rules
    if sale_in.payment_method == "cash":
        change_amount = sale_in.amount_received - sale_in.amount
    else:
        change_amount = 0.0

    # 3. Create sale record
    sale = CashRegisterSale(
        tenant_id=tenant_id,
        created_by_user_id=user_id,
        amount=sale_in.amount,
        amount_received=sale_in.amount_received,
        change_amount=change_amount,
        payment_method=sale_in.payment_method,
        status="completed",
        note=sale_in.note
    )
    db.add(sale)
    db.flush()

    # 4. Increment usage quota
    increment_usage(db, tenant_id, "cash_register_simple.sales.monthly", increment=1)

    # 5. Emit transactional outbox event
    emit_event(
        db=db,
        event_key="cash_register_simple.sale_created",
        payload={
            "sale_id": str(sale.id),
            "amount": float(sale.amount),
            "payment_method": sale.payment_method,
            "created_by_user_id": str(user_id)
        },
        tenant_id=tenant_id
    )

    # 6. Write audit log
    write_audit_log(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="cash_register.sale_created",
        payload={"sale_id": str(sale.id), "amount": float(sale.amount)}
    )

    return sale


def get_sales(
    db: Session,
    tenant_id: uuid.UUID,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[CashRegisterSale]:
    query = db.query(CashRegisterSale).filter(CashRegisterSale.tenant_id == tenant_id)
    if start_date:
        query = query.filter(func.cast(CashRegisterSale.created_at, Date) >= start_date)
    if end_date:
        query = query.filter(func.cast(CashRegisterSale.created_at, Date) <= end_date)
    return query.order_by(CashRegisterSale.created_at.desc()).all()


def get_sale_by_id(db: Session, tenant_id: uuid.UUID, sale_id: uuid.UUID) -> CashRegisterSale:
    sale = db.query(CashRegisterSale).filter(
        CashRegisterSale.id == sale_id,
        CashRegisterSale.tenant_id == tenant_id
    ).first()
    if not sale:
        raise NotFoundException("Sale not found", "SALE_NOT_FOUND")
    return sale


def cancel_sale(db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, sale_id: uuid.UUID, reason: str) -> CashRegisterSale:
    sale = get_sale_by_id(db, tenant_id, sale_id)
    if sale.status == "cancelled":
        return sale

    sale.status = "cancelled"
    sale.cancelled_at = datetime.now(timezone.utc)
    sale.cancelled_by_user_id = user_id
    sale.cancellation_reason = reason
    db.flush()

    # Emit event
    emit_event(
        db=db,
        event_key="cash_register_simple.sale_cancelled",
        payload={
            "sale_id": str(sale.id),
            "cancelled_by_user_id": str(user_id),
            "reason": reason
        },
        tenant_id=tenant_id
    )

    # Write audit log
    write_audit_log(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="cash_register.sale_cancelled",
        payload={"sale_id": str(sale.id), "reason": reason}
    )

    return sale


def create_day_closure(
    db: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    closure_in: DayClosureCreate
) -> CashRegisterDayClosure:
    # 1. Fetch non-cancelled sales for this tenant on the closing_date.
    # Use a day range instead of DATE casting so SQLite and PostgreSQL behave consistently.
    day_start = datetime.combine(closure_in.closing_date, datetime.min.time(), tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    sales = db.query(CashRegisterSale).filter(
        CashRegisterSale.tenant_id == tenant_id,
        CashRegisterSale.status != "cancelled",
        CashRegisterSale.created_at >= day_start,
        CashRegisterSale.created_at < day_end
    ).all()

    # 2. Compute totals
    total_sales_amount = float(sum(s.amount for s in sales))
    total_sales_count = len(sales)

    cash_total = float(sum(s.amount for s in sales if s.payment_method == "cash"))
    mobile_money_total = float(sum(s.amount for s in sales if s.payment_method == "mobile_money"))
    card_total = float(sum(s.amount for s in sales if s.payment_method == "card"))

    expected_cash_amount = cash_total
    difference_amount = closure_in.real_cash_amount - expected_cash_amount

    # 3. Create closure record
    closure = CashRegisterDayClosure(
        tenant_id=tenant_id,
        closed_by_user_id=user_id,
        closing_date=closure_in.closing_date,
        total_sales_amount=total_sales_amount,
        total_sales_count=total_sales_count,
        cash_total=cash_total,
        mobile_money_total=mobile_money_total,
        card_total=card_total,
        expected_cash_amount=expected_cash_amount,
        real_cash_amount=closure_in.real_cash_amount,
        difference_amount=difference_amount,
        note=closure_in.note
    )
    db.add(closure)
    db.flush()

    # 4. Emit event
    emit_event(
        db=db,
        event_key="cash_register_simple.day_closed",
        payload={
            "closure_id": str(closure.id),
            "closing_date": closure.closing_date.isoformat(),
            "total_sales_amount": float(closure.total_sales_amount),
            "closed_by_user_id": str(user_id)
        },
        tenant_id=tenant_id
    )

    # 5. Write audit log
    write_audit_log(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="cash_register.day_closed",
        payload={"closure_id": str(closure.id), "closing_date": closure.closing_date.isoformat()}
    )

    return closure


def get_closures(db: Session, tenant_id: uuid.UUID) -> List[CashRegisterDayClosure]:
    return db.query(CashRegisterDayClosure).filter(
        CashRegisterDayClosure.tenant_id == tenant_id
    ).order_by(CashRegisterDayClosure.closing_date.desc()).all()


def get_daily_report(db: Session, tenant_id: uuid.UUID, report_date: date) -> dict:
    day_start = datetime.combine(report_date, datetime.min.time(), tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    sales = db.query(CashRegisterSale).filter(
        CashRegisterSale.tenant_id == tenant_id,
        CashRegisterSale.status != "cancelled",
        CashRegisterSale.created_at >= day_start,
        CashRegisterSale.created_at < day_end
    ).all()

    total_sales_amount = float(sum(s.amount for s in sales))
    total_sales_count = len(sales)

    cash_total = float(sum(s.amount for s in sales if s.payment_method == "cash"))
    mobile_money_total = float(sum(s.amount for s in sales if s.payment_method == "mobile_money"))
    card_total = float(sum(s.amount for s in sales if s.payment_method == "card"))
    other_total = float(sum(s.amount for s in sales if s.payment_method == "other"))

    return {
        "date": report_date,
        "total_sales_amount": total_sales_amount,
        "total_sales_count": total_sales_count,
        "cash_total": cash_total,
        "mobile_money_total": mobile_money_total,
        "card_total": card_total,
        "other_total": other_total
    }
