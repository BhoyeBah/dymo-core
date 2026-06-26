import stripe
import structlog
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from dymo_saas_core.core.config import settings
from dymo_saas_core.models.models import Tenant
from dymo_saas_core.core.exceptions import AppException

logger = structlog.get_logger(__name__)

# Configure stripe API key if available
if settings.STRIPE_API_KEY:
    stripe.api_key = settings.STRIPE_API_KEY

def is_stripe_configured() -> bool:
    return bool(settings.STRIPE_API_KEY)

def get_or_create_stripe_customer(db: Session, tenant: Tenant) -> str:
    """Retrieve or create a Stripe Customer for the tenant."""
    if not is_stripe_configured():
        if not tenant.stripe_customer_id:
            tenant.stripe_customer_id = f"cus_mock_{tenant.id.hex[:12]}"
            db.commit()
        return tenant.stripe_customer_id

    if tenant.stripe_customer_id:
        return tenant.stripe_customer_id

    try:
        customer = stripe.Customer.create(
            email=tenant.owner_email,
            name=tenant.name,
            metadata={"tenant_id": str(tenant.id)}
        )
        tenant.stripe_customer_id = customer.id
        db.commit()
        logger.info("Created Stripe customer", tenant_id=str(tenant.id), customer_id=customer.id)
        return customer.id
    except Exception as e:
        logger.error("Failed to create Stripe customer", tenant_id=str(tenant.id), error=str(e))
        raise AppException(f"Stripe customer creation failed: {str(e)}", "STRIPE_ERROR")

def create_checkout_session(
    db: Session,
    tenant: Tenant,
    price_id: str,
    billing_cycle: str,
    success_url: str,
    cancel_url: str
) -> Dict[str, Any]:
    """Create a Stripe Checkout Session for subscription."""
    customer_id = get_or_create_stripe_customer(db, tenant)

    if not is_stripe_configured():
        mock_session_id = f"cs_mock_{tenant.id.hex[:12]}_{price_id[:6]}"
        mock_url = f"https://mock-checkout.stripe.com/pay/{mock_session_id}?success={success_url}&cancel={cancel_url}"
        logger.info("Stripe not configured. Creating mock checkout session.", tenant_id=str(tenant.id), price_id=price_id)
        return {
            "id": mock_session_id,
            "url": mock_url
        }

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price": price_id,
                "quantity": 1
            }],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "tenant_id": str(tenant.id),
                "stripe_price_id": price_id,
                "billing_cycle": billing_cycle
            },
            subscription_data={
                "metadata": {
                    "tenant_id": str(tenant.id)
                }
            }
        )
        logger.info("Created Stripe checkout session", tenant_id=str(tenant.id), session_id=session.id)
        return {
            "id": session.id,
            "url": session.url
        }
    except Exception as e:
        logger.error("Failed to create Stripe checkout session", tenant_id=str(tenant.id), error=str(e))
        raise AppException(f"Stripe checkout session creation failed: {str(e)}", "STRIPE_ERROR")

def create_billing_portal_session(tenant: Tenant, return_url: str) -> Dict[str, Any]:
    """Create a Stripe Customer Billing Portal session."""
    if not tenant.stripe_customer_id:
        raise AppException("No Stripe customer profile found for this tenant", "STRIPE_CUSTOMER_NOT_FOUND")

    if not is_stripe_configured():
        mock_url = f"https://mock-billing-portal.stripe.com/p/session/{tenant.stripe_customer_id}?return={return_url}"
        logger.info("Stripe not configured. Creating mock billing portal session.", tenant_id=str(tenant.id))
        return {
            "url": mock_url
        }

    try:
        session = stripe.billing_portal.Session.create(
            customer=tenant.stripe_customer_id,
            return_url=return_url
        )
        logger.info("Created Stripe billing portal session", tenant_id=str(tenant.id), portal_session_id=session.id)
        return {
            "url": session.url
        }
    except Exception as e:
        logger.error("Failed to create Stripe billing portal session", tenant_id=str(tenant.id), error=str(e))
        raise AppException(f"Stripe portal session creation failed: {str(e)}", "STRIPE_ERROR")
