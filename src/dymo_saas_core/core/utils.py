import structlog
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from dymo_saas_core.models.models import TenantAuditLog

logger = structlog.get_logger(__name__)

def write_audit_log(
    db: Session,
    tenant_id: Any,
    user_id: Any,
    action: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None
) -> TenantAuditLog:
    """Write an audit log entry for a tenant action."""
    log = TenantAuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        ip_address=ip_address,
        user_agent=user_agent,
        payload=payload or {}
    )
    db.add(log)
    db.commit()
    logger.info("Audit log written", tenant_id=str(tenant_id), user_id=str(user_id), action=action)
    return log

def send_email(to_email: str, subject: str, body: str, template_id: Optional[str] = None) -> bool:
    """Send email via Brevo API / SMTP or fallback mock."""
    from dymo_saas_core.integrations.emails.brevo import send_brevo_email
    return send_brevo_email(to_email, subject, body, template_id)

def send_sms(to_phone: str, message: str) -> bool:
    """Send SMS via Twilio API or fallback mock."""
    from dymo_saas_core.integrations.sms.twilio import send_twilio_sms
    return send_twilio_sms(to_phone, message)

def create_payment_link(tenant_id: Any, amount: float, currency: str, description: str) -> Dict[str, str]:
    """Create Stripe Checkout Session for a single payment, or fallback mock."""
    from dymo_saas_core.integrations.payments.stripe import is_stripe_configured
    import stripe
    
    if is_stripe_configured():
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": currency.lower(),
                        "product_data": {
                            "name": description,
                        },
                        "unit_amount": int(amount * 100),
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url="https://dymo-saas.com/payment/success",
                cancel_url="https://dymo-saas.com/payment/cancel",
                metadata={
                    "tenant_id": str(tenant_id),
                    "type": "one_time_payment"
                }
            )
            logger.info("Created one-time Stripe checkout session", tenant_id=str(tenant_id), session_id=session.id)
            return {"payment_url": session.url}
        except Exception as e:
            logger.error("Failed to create one-time Stripe checkout session", tenant_id=str(tenant_id), error=str(e))
            
    # Mock fallback
    logger.info("Creating payment link (mocked)", tenant_id=str(tenant_id), amount=amount, currency=currency)
    return {
        "payment_url": f"https://mock-payment-gateway.dymo.com/pay/{tenant_id}?amount={amount}&currency={currency}"
    }
