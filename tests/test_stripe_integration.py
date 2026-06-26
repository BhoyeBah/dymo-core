import pytest
import uuid
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from dymo_saas_core.models.models import (
    PlatformAdmin, Plan, PlanPrice, PlanLimit, Subscription,
    Tenant, TenantUser, BillingInvoice, BillingPayment, SubscriptionEvent
)
from dymo_saas_core.core.security import hash_password
from dymo_saas_core.core.module_registry import sync_modules_to_database
from dymo_saas_core.core.utils import send_email, send_sms

@pytest.fixture(autouse=True)
def seed_billing_test_data(db_session):
    """Seed test-specific database tables within the test transaction."""
    # 1. Seed Platform Admin
    admin = PlatformAdmin(
        email="admin@dymo.com",
        password_hash=hash_password("DymoAdmin2026!"),
        first_name="Super",
        last_name="Admin",
        is_active=True
    )
    db_session.add(admin)
    
    # 2. Sync available modules
    sync_modules_to_database(db_session)
    
    # 3. Seed Plan
    plan = Plan(
        name="Pro Plan",
        slug="pro",
        description="Premium features for growing businesses",
        status="active",
        trial_enabled=True,
        trial_days=14,
        display_order=1
    )
    db_session.add(plan)
    db_session.flush()
    
    # Add Price
    price = PlanPrice(
        plan_id=plan.id,
        billing_cycle="monthly",
        currency="EUR",
        amount=99.00,
        stripe_price_id="price_stripe_pro_monthly"
    )
    db_session.add(price)
    db_session.commit()

@pytest.fixture
def billing_tenant(client, db_session):
    """Provision a tenant for billing tests."""
    # 1. Platform Admin Login
    login_resp = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    admin_token = login_resp.json()["data"]["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 2. Provision Tenant
    prov_resp = client.post("/api/v1/platform/tenants", json={
        "name": "Acme Billing",
        "slug": "acmebill",
        "owner_email": "owner@acmebill.com",
        "owner_phone": "+33612345688",
        "country": "France",
        "currency": "EUR",
        "timezone": "Europe/Paris",
        "language": "fr"
    }, headers=admin_headers)
    tenant_id = uuid.UUID(prov_resp.json()["data"]["id"])
    
    # Owner login
    login_owner = client.post("/api/v1/app/auth/login", json={
        "email": "owner@acmebill.com",
        "password": "ChangeMe123!"
    }, headers={"X-Tenant-Slug": "acmebill"})
    owner_token = login_owner.json()["data"]["access_token"]
    
    return {
        "id": tenant_id,
        "token": owner_token,
        "slug": "acmebill"
    }

def test_stripe_checkout_and_portal_flows(client, billing_tenant, db_session):
    headers = {
        "Authorization": f"Bearer {billing_tenant['token']}",
        "X-Tenant-Slug": billing_tenant["slug"]
    }
    
    plan = db_session.query(Plan).filter(Plan.slug == "pro").first()
    
    # 1. Portal session should fail initially when no customer profile exists
    portal_resp = client.post(
        "/api/v1/app/billing/subscription/portal-session",
        json={"return_url": "https://example.com/return"},
        headers=headers
    )
    assert portal_resp.status_code == 400
    assert "NO_BILLING_PROFILE" in portal_resp.json()["error_code"]

    # 2. Try checkout session creation, which triggers customer profile creation
    checkout_resp = client.post(
        "/api/v1/app/billing/subscription/checkout-session",
        json={
            "plan_id": str(plan.id),
            "billing_cycle": "monthly",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel"
        },
        headers=headers
    )
    assert checkout_resp.status_code == 200
    checkout_data = checkout_resp.json()["data"]
    assert "url" in checkout_data
    assert "mock-checkout" in checkout_data["url"]
    
    # 3. Portal session succeeds now that the customer profile exists
    portal_resp_2 = client.post(
        "/api/v1/app/billing/subscription/portal-session",
        json={"return_url": "https://example.com/return"},
        headers=headers
    )
    assert portal_resp_2.status_code == 200
    portal_data = portal_resp_2.json()["data"]
    assert "url" in portal_data
    assert "mock-billing-portal" in portal_data["url"]

def test_stripe_webhook_checkout_session_completed(client, billing_tenant, db_session):
    payload = {
        "id": "evt_checkout_completed",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_checkout123",
                "customer": "cus_stripe_acme_1",
                "subscription": "sub_stripe_acme_1",
                "metadata": {
                    "tenant_id": str(billing_tenant["id"]),
                    "stripe_price_id": "price_stripe_pro_monthly",
                    "billing_cycle": "monthly"
                }
            }
        }
    }
    
    resp = client.post("/api/v1/billing/webhooks/stripe", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {"status": "success"}
    
    db_session.commit()
    
    # Check tenant status updated to active
    tenant = db_session.query(Tenant).filter(Tenant.id == billing_tenant["id"]).first()
    assert tenant.status == "active"
    assert tenant.stripe_customer_id == "cus_stripe_acme_1"
    
    # Check subscription created
    sub = db_session.query(Subscription).filter(Subscription.tenant_id == billing_tenant["id"]).first()
    assert sub is not None
    assert sub.status == "active"
    assert sub.stripe_subscription_id == "sub_stripe_acme_1"
    
    # Check subscription event
    event = db_session.query(SubscriptionEvent).filter(SubscriptionEvent.tenant_id == billing_tenant["id"]).first()
    assert event is not None
    assert event.event_type == "created"

def test_stripe_webhook_invoice_paid(client, billing_tenant, db_session):
    # Establish subscription first
    plan = db_session.query(Plan).filter(Plan.slug == "pro").first()
    sub = Subscription(
        tenant_id=billing_tenant["id"],
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        stripe_subscription_id="sub_stripe_acme_2",
        current_period_start=datetime.now(timezone.utc) - timedelta(days=5),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=25)
    )
    db_session.add(sub)
    db_session.commit()
    
    payload = {
        "id": "evt_invoice_paid",
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": "in_stripe_invoice_99",
                "subscription": "sub_stripe_acme_2",
                "customer": "cus_stripe_acme_1",
                "number": "INV-PRO-99",
                "currency": "eur",
                "total": 9900,
                "amount_paid": 9900,
                "amount_due": 0,
                "period_start": int(datetime.now().timestamp()),
                "period_end": int((datetime.now() + timedelta(days=30)).timestamp()),
                "hosted_invoice_url": "https://stripe.com/invoice/pdf/99"
            }
        }
    }
    
    resp = client.post("/api/v1/billing/webhooks/stripe", json=payload)
    assert resp.status_code == 200
    
    db_session.commit()
    
    # Verify invoice was created in DB
    invoice = db_session.query(BillingInvoice).filter(BillingInvoice.stripe_invoice_id == "in_stripe_invoice_99").first()
    assert invoice is not None
    assert invoice.invoice_number == "INV-PRO-99"
    assert invoice.status == "paid"
    assert invoice.total_amount == 99.00
    
    # Verify payment recorded
    payment = db_session.query(BillingPayment).filter(BillingPayment.invoice_id == invoice.id).first()
    assert payment is not None
    assert payment.amount == 99.00
    assert payment.payment_method == "stripe"

def test_stripe_webhook_invoice_payment_failed(client, billing_tenant, db_session):
    # Establish subscription first
    plan = db_session.query(Plan).filter(Plan.slug == "pro").first()
    sub = Subscription(
        tenant_id=billing_tenant["id"],
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        stripe_subscription_id="sub_stripe_acme_3",
        current_period_start=datetime.now(timezone.utc) - timedelta(days=5),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=25)
    )
    db_session.add(sub)
    db_session.commit()
    
    payload = {
        "id": "evt_invoice_failed",
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": "in_stripe_invoice_failed_1",
                "subscription": "sub_stripe_acme_3",
                "customer": "cus_stripe_acme_1"
            }
        }
    }
    
    resp = client.post("/api/v1/billing/webhooks/stripe", json=payload)
    assert resp.status_code == 200
    
    db_session.commit()
    db_session.refresh(sub)
    assert sub.status == "past_due"
    
    # Check subscription event
    event = db_session.query(SubscriptionEvent).filter(
        SubscriptionEvent.tenant_id == billing_tenant["id"],
        SubscriptionEvent.event_type == "payment_failed"
    ).first()
    assert event is not None

def test_stripe_webhook_subscription_deleted(client, billing_tenant, db_session):
    # Establish subscription first
    plan = db_session.query(Plan).filter(Plan.slug == "pro").first()
    sub = Subscription(
        tenant_id=billing_tenant["id"],
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        stripe_subscription_id="sub_stripe_acme_4",
        current_period_start=datetime.now(timezone.utc) - timedelta(days=5),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=25)
    )
    db_session.add(sub)
    db_session.commit()
    
    payload = {
        "id": "evt_sub_deleted",
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_stripe_acme_4"
            }
        }
    }
    
    resp = client.post("/api/v1/billing/webhooks/stripe", json=payload)
    assert resp.status_code == 200
    
    db_session.commit()
    db_session.refresh(sub)
    assert sub.status == "cancelled"
    
    tenant = db_session.query(Tenant).filter(Tenant.id == billing_tenant["id"]).first()
    assert tenant.status == "suspended"

def test_notification_fallbacks():
    # Verify fallback helper functions execute and return True
    assert send_email("test@example.com", "Test Subject", "<p>Hello</p>") is True
    assert send_sms("+33600000000", "SMS message text") is True
