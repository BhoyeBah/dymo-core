from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.exceptions import AppException, NotFoundException
from dymo_saas_core.core.pagination import paginate_query
from dymo_saas_core.core.platform_context import require_platform_admin
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.models.models import BillingInvoice, BillingPayment, Tenant, PlatformAuditLog
from dymo_saas_core.platform.schemas import PaymentRefundRequest, PaymentRetryRequest

router = APIRouter(tags=["Platform Payments"])


def _payment_payload(payment: BillingPayment, db: Session) -> dict:
    invoice = db.query(BillingInvoice).filter(BillingInvoice.id == payment.invoice_id).first()
    tenant = db.query(Tenant).filter(Tenant.id == invoice.tenant_id).first() if invoice else None
    return {
        "id": str(payment.id),
        "tenant_id": str(payment.tenant_id),
        "tenant_name": tenant.name if tenant else None,
        "invoice_id": str(payment.invoice_id),
        "invoice_number": invoice.invoice_number if invoice else None,
        "provider_reference": payment.provider_reference,
        "payment_method": payment.payment_method,
        "amount": float(payment.amount),
        "currency": payment.currency,
        "status": payment.status,
        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
        "error_message": payment.error_message,
        "created_at": payment.created_at.isoformat(),
        "updated_at": payment.updated_at.isoformat(),
    }


def _invoice_payload(invoice: BillingInvoice, db: Session) -> dict:
    tenant = db.query(Tenant).filter(Tenant.id == invoice.tenant_id).first()
    return {
        "id": str(invoice.id),
        "tenant_id": str(invoice.tenant_id),
        "tenant_name": tenant.name if tenant else None,
        "invoice_number": invoice.invoice_number,
        "subscription_id": str(invoice.subscription_id) if invoice.subscription_id else None,
        "status": invoice.status,
        "currency": invoice.currency,
        "subtotal_amount": float(invoice.subtotal_amount),
        "tax_amount": float(invoice.tax_amount),
        "discount_amount": float(invoice.discount_amount),
        "total_amount": float(invoice.total_amount),
        "amount_paid": float(invoice.amount_paid),
        "amount_due": float(invoice.amount_due),
        "due_date": invoice.due_date.isoformat(),
        "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
        "period_start": invoice.period_start.isoformat(),
        "period_end": invoice.period_end.isoformat(),
        "pdf_url": invoice.pdf_url,
        "created_at": invoice.created_at.isoformat(),
        "updated_at": invoice.updated_at.isoformat(),
    }


def _write_platform_audit_log(db: Session, admin_id: uuid.UUID | None, action: str, payload: dict) -> None:
    db.add(
        PlatformAuditLog(
            admin_id=admin_id,
            action=action,
            payload=payload,
        )
    )


@router.get("/payments")
def list_payments(
    tenant_id: uuid.UUID | None = None,
    provider: str | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin),
):
    query = db.query(BillingPayment).order_by(BillingPayment.created_at.desc())
    if tenant_id is not None:
        query = query.filter(BillingPayment.tenant_id == tenant_id)
    if provider:
        query = query.filter(BillingPayment.payment_method == provider)
    if status:
        query = query.filter(BillingPayment.status == status)
    payments, meta = paginate_query(db, query, page, per_page)
    return success_response([_payment_payload(payment, db) for payment in payments], meta=meta)


@router.get("/payments/{payment_id}")
def get_payment(payment_id: uuid.UUID, db: Session = Depends(get_db), admin = Depends(require_platform_admin)):
    payment = db.query(BillingPayment).filter(BillingPayment.id == payment_id).first()
    if not payment:
        raise NotFoundException("Payment not found", "PAYMENT_NOT_FOUND")
    return success_response(_payment_payload(payment, db))


@router.post("/payments/{payment_id}/retry")
def retry_payment(
    payment_id: uuid.UUID,
    body: PaymentRetryRequest,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin),
):
    payment = db.query(BillingPayment).filter(BillingPayment.id == payment_id).first()
    if not payment:
        raise NotFoundException("Payment not found", "PAYMENT_NOT_FOUND")
    if payment.status not in {"failed", "cancelled", "expired"}:
        raise AppException("Only failed, cancelled or expired payments can be retried", "PAYMENT_RETRY_NOT_ALLOWED", 409)

    payment.status = "pending"
    payment.error_message = None
    payment.paid_at = None
    _write_platform_audit_log(
        db=db,
        admin_id=admin.id,
        action="payment_retried",
        payload={"payment_id": str(payment.id), "reason": body.reason},
    )
    db.commit()
    return success_response(_payment_payload(payment, db), message="Payment queued for retry")


@router.post("/payments/{payment_id}/refund")
def refund_payment(
    payment_id: uuid.UUID,
    body: PaymentRefundRequest,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin),
):
    payment = db.query(BillingPayment).filter(BillingPayment.id == payment_id).first()
    if not payment:
        raise NotFoundException("Payment not found", "PAYMENT_NOT_FOUND")
    if payment.status not in {"completed", "successful", "refunded"}:
        raise AppException("Only completed payments can be refunded", "PAYMENT_REFUND_NOT_ALLOWED", 409)

    refund_amount = body.amount if body.amount is not None else float(payment.amount)
    if refund_amount <= 0 or refund_amount > float(payment.amount):
        raise AppException("Invalid refund amount", "INVALID_REFUND_AMOUNT", 400)

    payment.status = "refunded"
    payment.error_message = body.reason
    payment.paid_at = payment.paid_at or datetime.now(timezone.utc)

    invoice = db.query(BillingInvoice).filter(BillingInvoice.id == payment.invoice_id).first()
    if invoice:
        invoice.status = "refunded"
        invoice.amount_paid = float(invoice.amount_paid) - refund_amount
        if invoice.amount_paid < 0:
            invoice.amount_paid = 0.0
        invoice.amount_due = float(invoice.total_amount) - float(invoice.amount_paid)

    _write_platform_audit_log(
        db=db,
        admin_id=admin.id,
        action="payment_refunded",
        payload={"payment_id": str(payment.id), "amount": refund_amount, "reason": body.reason},
    )
    db.commit()
    return success_response(_payment_payload(payment, db), message="Payment refunded successfully")


@router.get("/invoices")
def list_invoices(
    tenant_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin),
):
    query = db.query(BillingInvoice).order_by(BillingInvoice.created_at.desc())
    if tenant_id is not None:
        query = query.filter(BillingInvoice.tenant_id == tenant_id)
    if status:
        query = query.filter(BillingInvoice.status == status)
    invoices, meta = paginate_query(db, query, page, per_page)
    return success_response([_invoice_payload(invoice, db) for invoice in invoices], meta=meta)


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db), admin = Depends(require_platform_admin)):
    invoice = db.query(BillingInvoice).filter(BillingInvoice.id == invoice_id).first()
    if not invoice:
        raise NotFoundException("Invoice not found", "INVOICE_NOT_FOUND")
    return success_response(_invoice_payload(invoice, db))
