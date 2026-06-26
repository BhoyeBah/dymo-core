from datetime import datetime, timezone, timedelta
import uuid

import pytest

from dymo_saas_core.core.module_registry import sync_modules_to_database
from dymo_saas_core.core.security import hash_password
from dymo_saas_core.core.encryption import decrypt_secret
from dymo_saas_core.models.models import (
    BillingInvoice,
    BillingPayment,
    Plan,
    Subscription,
    Tenant,
    PlatformProviderConfig,
    PlatformAdmin,
    PlanPrice,
    PlanLimit,
    PlanModule,
)


@pytest.fixture(autouse=True)
def seed_platform_data(db_session):
    admin = PlatformAdmin(
        email="admin@dymo.com",
        password_hash=hash_password("DymoAdmin2026!"),
        first_name="Super",
        last_name="Admin",
        is_active=True,
    )
    db_session.add(admin)
    sync_modules_to_database(db_session)

    plan = Plan(
        name="Standard Plan",
        slug="standard",
        description="Plan standard",
        status="active",
        trial_enabled=True,
        trial_days=14,
        display_order=1,
    )
    db_session.add(plan)
    db_session.flush()
    db_session.add_all(
        [
            PlanPrice(plan_id=plan.id, billing_cycle="monthly", currency="EUR", amount=49.0),
            PlanLimit(plan_id=plan.id, metric_key="max_users", limit_value=3, period="monthly"),
            PlanModule(plan_id=plan.id, module_key="cash_register_simple"),
        ]
    )
    db_session.commit()


def _login_admin(client):
    login_resp = client.post(
        "/api/v1/platform/auth/login",
        json={"email": "admin@dymo.com", "password": "DymoAdmin2026!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_tenant(client, headers, slug="omega", owner_email="owner@omega.com"):
    resp = client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Omega Corp",
            "slug": slug,
            "owner_email": owner_email,
            "country": "Senegal",
            "currency": "XOF",
            "timezone": "Africa/Dakar",
            "language": "fr",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()["data"]


def test_platform_providers_routes_mask_credentials(client, db_session):
    headers = _login_admin(client)

    create_resp = client.post(
        "/api/v1/platform/providers",
        json={
            "provider_type": "payment",
            "provider_name": "Stripe",
            "environment": "production",
            "credentials": {"api_key": "sk_live_1234567890", "secret": "topsecret"},
            "is_active": True,
            "is_default": True,
            "supported_countries": ["SN", "CI"],
            "supported_currencies": ["XOF", "EUR"],
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    provider = create_resp.json()["data"]
    assert provider["credentials_masked"]["api_key"].startswith("****")
    assert provider["credentials_masked"]["secret"].startswith("****")

    provider_id = provider["id"]
    get_resp = client.get(f"/api/v1/platform/providers/{provider_id}", headers=headers)
    assert get_resp.status_code == 200
    assert "sk_live_1234567890" not in str(get_resp.json())

    patch_resp = client.patch(
        f"/api/v1/platform/providers/{provider_id}",
        json={"is_active": False},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["is_active"] is False

    test_resp = client.post(
        f"/api/v1/platform/providers/{provider_id}/test",
        json={"payload": {"ping": True}},
        headers=headers,
    )
    assert test_resp.status_code == 409
    assert test_resp.json()["error_code"] == "PROVIDER_INACTIVE"

    log_resp = client.get("/api/v1/platform/provider-logs", headers=headers)
    assert log_resp.status_code == 200
    assert len(log_resp.json()["data"]) >= 1

    db_provider = db_session.query(PlatformProviderConfig).filter(PlatformProviderConfig.id == uuid.UUID(provider_id)).first()
    assert db_provider is not None
    assert decrypt_secret(db_provider.encrypted_credentials) != db_provider.encrypted_credentials
    assert "sk_live_1234567890" in decrypt_secret(db_provider.encrypted_credentials)


def test_platform_payments_invoices_analytics_and_audit_logs(client, db_session):
    headers = _login_admin(client)
    tenant_data = _create_tenant(client, headers, slug="theta", owner_email="owner@theta.com")
    tenant = db_session.query(Tenant).filter(Tenant.slug == "theta").first()
    plan = db_session.query(Plan).filter(Plan.slug == "standard").first()
    assert tenant is not None
    assert plan is not None

    subscription = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        current_period_start=datetime.now(timezone.utc) - timedelta(days=5),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=25),
    )
    db_session.add(subscription)
    db_session.flush()

    completed_invoice = BillingInvoice(
        tenant_id=tenant.id,
        subscription_id=subscription.id,
        invoice_number="INV-1001",
        status="paid",
        currency="XOF",
        subtotal_amount=49.0,
        tax_amount=0.0,
        discount_amount=0.0,
        total_amount=49.0,
        amount_paid=49.0,
        amount_due=0.0,
        due_date=datetime.now(timezone.utc) + timedelta(days=7),
        paid_at=datetime.now(timezone.utc),
        period_start=datetime.now(timezone.utc) - timedelta(days=5),
        period_end=datetime.now(timezone.utc) + timedelta(days=25),
    )
    failed_invoice = BillingInvoice(
        tenant_id=tenant.id,
        subscription_id=subscription.id,
        invoice_number="INV-1002",
        status="open",
        currency="XOF",
        subtotal_amount=19.0,
        tax_amount=0.0,
        discount_amount=0.0,
        total_amount=19.0,
        amount_paid=0.0,
        amount_due=19.0,
        due_date=datetime.now(timezone.utc) + timedelta(days=7),
        period_start=datetime.now(timezone.utc) - timedelta(days=5),
        period_end=datetime.now(timezone.utc) + timedelta(days=25),
    )
    db_session.add_all([completed_invoice, failed_invoice])
    db_session.flush()

    completed_payment = BillingPayment(
        tenant_id=tenant.id,
        invoice_id=completed_invoice.id,
        provider_reference="pay_1001",
        payment_method="stripe",
        amount=49.0,
        currency="XOF",
        status="completed",
        paid_at=datetime.now(timezone.utc),
    )
    failed_payment = BillingPayment(
        tenant_id=tenant.id,
        invoice_id=failed_invoice.id,
        provider_reference="pay_1002",
        payment_method="wave",
        amount=19.0,
        currency="XOF",
        status="failed",
        error_message="insufficient_funds",
    )
    db_session.add_all([completed_payment, failed_payment])
    db_session.commit()

    payments_resp = client.get("/api/v1/platform/payments", headers=headers)
    assert payments_resp.status_code == 200
    assert len(payments_resp.json()["data"]) >= 2

    invoices_resp = client.get("/api/v1/platform/invoices", headers=headers)
    assert invoices_resp.status_code == 200
    assert len(invoices_resp.json()["data"]) >= 2

    payment_detail = client.get(f"/api/v1/platform/payments/{failed_payment.id}", headers=headers)
    assert payment_detail.status_code == 200
    assert payment_detail.json()["data"]["status"] == "failed"

    retry_resp = client.post(
        f"/api/v1/platform/payments/{failed_payment.id}/retry",
        json={"reason": "manual_retry"},
        headers=headers,
    )
    assert retry_resp.status_code == 200
    assert retry_resp.json()["data"]["status"] == "pending"

    refund_resp = client.post(
        f"/api/v1/platform/payments/{completed_payment.id}/refund",
        json={"reason": "customer_request"},
        headers=headers,
    )
    assert refund_resp.status_code == 200
    assert refund_resp.json()["data"]["status"] == "refunded"

    analytics_resp = client.get("/api/v1/platform/analytics/overview", headers=headers)
    assert analytics_resp.status_code == 200
    analytics = analytics_resp.json()["data"]
    assert "mrr" in analytics
    assert "arr" in analytics
    assert "revenue_by_provider" in analytics

    dashboard_resp = client.get("/api/v1/platform/dashboard", headers=headers)
    assert dashboard_resp.status_code == 200

    revenue_resp = client.get("/api/v1/platform/analytics/revenue", headers=headers)
    assert revenue_resp.status_code == 200

    tenants_resp = client.get("/api/v1/platform/analytics/tenants", headers=headers)
    assert tenants_resp.status_code == 200

    providers_resp = client.get("/api/v1/platform/analytics/providers", headers=headers)
    assert providers_resp.status_code == 200

    usage_resp = client.get("/api/v1/platform/analytics/usage", headers=headers)
    assert usage_resp.status_code == 200

    audit_resp = client.get("/api/v1/platform/audit-logs", headers=headers)
    assert audit_resp.status_code == 200
    assert len(audit_resp.json()["data"]) >= 1
