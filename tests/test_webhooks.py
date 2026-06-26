import pytest
import uuid
import hmac
import hashlib
import time
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import httpx

from dymo_saas_core.core.cache import cache_service
from dymo_saas_core.models.models import (
    PlatformAdmin, Plan, PlanPrice, PlanLimit, PlanModule, Subscription,
    Tenant, TenantUser, WebhookSubscription, WebhookDelivery, OutboxEvent
)
from dymo_saas_core.core.security import hash_password
from dymo_saas_core.core.module_registry import sync_modules_to_database
from dymo_saas_core.core.encryption import decrypt_secret
from dymo_saas_core.core.webhook_dispatcher import calculate_signature
from dymo_saas_core.jobs.outbox_worker import OutboxWorker

@pytest.fixture(autouse=True)
def seed_test_data(db_session):
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
        name="Standard Plan",
        slug="standard",
        description="Idéal pour les petites et moyennes entreprises",
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
        amount=49.00
    )
    db_session.add(price)
    
    # Add Limit
    limit = PlanLimit(
        plan_id=plan.id,
        metric_key="max_users",
        limit_value=3,
        period="monthly"
    )
    db_session.add(limit)
    
    # Add Module
    pm = PlanModule(
        plan_id=plan.id,
        module_key="cash_register_simple"
    )
    db_session.add(pm)
    
    db_session.commit()

@pytest.fixture
def provisioned_tenants(client, db_session):
    """Provision two tenants for testing isolation."""
    # 1. Platform Admin Login
    login_resp = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    admin_token = login_resp.json()["data"]["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 2. Provision Tenant A
    prov_resp_a = client.post("/api/v1/platform/tenants", json={
        "name": "Tenant A",
        "slug": "tenanta",
        "owner_email": "owner@tenanta.com",
        "owner_phone": "+33612345671",
        "country": "France",
        "currency": "EUR",
        "timezone": "Europe/Paris",
        "language": "fr"
    }, headers=admin_headers)
    tenant_a_id = uuid.UUID(prov_resp_a.json()["data"]["id"])
    
    # 3. Provision Tenant B
    prov_resp_b = client.post("/api/v1/platform/tenants", json={
        "name": "Tenant B",
        "slug": "tenantb",
        "owner_email": "owner@tenantb.com",
        "owner_phone": "+33612345672",
        "country": "France",
        "currency": "EUR",
        "timezone": "Europe/Paris",
        "language": "fr"
    }, headers=admin_headers)
    tenant_b_id = uuid.UUID(prov_resp_b.json()["data"]["id"])
    
    # Subscribe both to Standard Plan
    plan = db_session.query(Plan).filter(Plan.slug == "standard").first()
    sub_a = Subscription(
        tenant_id=tenant_a_id,
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30)
    )
    sub_b = Subscription(
        tenant_id=tenant_b_id,
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db_session.add(sub_a)
    db_session.add(sub_b)
    db_session.commit()
    
    # Owner login A
    login_a = client.post("/api/v1/app/auth/login", json={
        "email": "owner@tenanta.com",
        "password": "ChangeMe123!"
    }, headers={"X-Tenant-Slug": "tenanta"})
    owner_token_a = login_a.json()["data"]["access_token"]
    
    # Owner login B
    login_b = client.post("/api/v1/app/auth/login", json={
        "email": "owner@tenantb.com",
        "password": "ChangeMe123!"
    }, headers={"X-Tenant-Slug": "tenantb"})
    owner_token_b = login_b.json()["data"]["access_token"]
    
    return {
        "tenant_a": {"id": tenant_a_id, "token": owner_token_a, "slug": "tenanta"},
        "tenant_b": {"id": tenant_b_id, "token": owner_token_b, "slug": "tenantb"}
    }

def test_webhook_subscription_crud(client, provisioned_tenants):
    headers_a = {
        "Authorization": f"Bearer {provisioned_tenants['tenant_a']['token']}",
        "X-Tenant-Slug": "tenanta"
    }

    # 1. Create Webhook Subscription
    create_resp = client.post("/api/v1/app/webhooks", json={
        "name": "Acme Webhook",
        "target_url": "https://example.com/webhook",
        "events": ["cash_register_simple.sale_created", "ping"]
    }, headers=headers_a)
    assert create_resp.status_code == 201
    data = create_resp.json()["data"]
    assert "secret" in data
    assert len(data["secret"]) == 64
    assert data["name"] == "Acme Webhook"
    assert data["events"] == ["cash_register_simple.sale_created", "ping"]
    sub_id = data["id"]

    # 2. List Webhooks
    list_resp = client.get("/api/v1/app/webhooks", headers=headers_a)
    assert list_resp.status_code == 200
    list_data = list_resp.json()["data"]
    assert len(list_data) == 1
    assert "secret" not in list_data[0] # secret must be private
    assert list_data[0]["id"] == sub_id

    # 3. Get Webhook details
    get_resp = client.get(f"/api/v1/app/webhooks/{sub_id}", headers=headers_a)
    assert get_resp.status_code == 200
    get_data = get_resp.json()["data"]
    assert "secret" not in get_data
    assert get_data["name"] == "Acme Webhook"

    # 4. Update Webhook subscription
    update_resp = client.patch(f"/api/v1/app/webhooks/{sub_id}", json={
        "status": "inactive"
    }, headers=headers_a)
    assert update_resp.status_code == 200
    update_data = update_resp.json()["data"]
    assert update_data["status"] == "inactive"
    assert update_data["disabled_at"] is not None

    # 5. Delete Webhook subscription
    del_resp = client.delete(f"/api/v1/app/webhooks/{sub_id}", headers=headers_a)
    assert del_resp.status_code == 200
    assert "deleted successfully" in del_resp.json()["message"]

def test_webhook_signature_and_delivery(client, provisioned_tenants, db_session):
    headers_a = {
        "Authorization": f"Bearer {provisioned_tenants['tenant_a']['token']}",
        "X-Tenant-Slug": "tenanta"
    }

    # Create subscription
    create_resp = client.post("/api/v1/app/webhooks", json={
        "name": "Signature Test",
        "target_url": "https://httpbin.org/post",
        "events": ["ping"]
    }, headers=headers_a)
    assert create_resp.status_code == 201
    sub_data = create_resp.json()["data"]
    sub_id = uuid.UUID(sub_data["id"])
    raw_secret = sub_data["secret"]

    original_post = httpx.Client.post
    mock_calls = []

    def side_effect_post(self, url, *args, **kwargs):
        if "httpbin.org" in str(url) or "example.com" in str(url):
            mock_calls.append((str(url), kwargs))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            return mock_resp
        return original_post(self, url, *args, **kwargs)

    # Trigger test webhook ping (which fires BackgroundTask)
    with patch("httpx.Client.post", side_effect=side_effect_post, autospec=True):
        test_resp = client.post(f"/api/v1/app/webhooks/{sub_id}/test", headers=headers_a)
        assert test_resp.status_code == 200
        delivery_id = test_resp.json()["data"]["delivery_id"]

    # Validate headers and payload signature
    assert len(mock_calls) == 1
    target_url, call_kwargs = mock_calls[0]
    content = call_kwargs["content"]
    headers = call_kwargs["headers"]

    assert target_url == "https://httpbin.org/post"
    assert headers["X-Dymo-Event"] == "ping"
    assert headers["X-Dymo-Delivery-Id"] == delivery_id
    
    # Verify calculated signature matches header
    expected_sig = calculate_signature(raw_secret, headers["X-Dymo-Timestamp"], content)
    assert headers["X-Dymo-Signature"] == expected_sig

    # Fetch deliveries and verify status in DB
    db_session.commit()
    del_resp = client.get(f"/api/v1/app/webhooks/{sub_id}/deliveries", headers=headers_a)
    assert del_resp.status_code == 200
    deliveries = del_resp.json()["data"]
    assert len(deliveries) == 1
    assert deliveries[0]["status"] == "delivered"
    assert deliveries[0]["last_status_code"] == 200

def test_webhook_retry_backoff(client, provisioned_tenants, db_session):
    headers_a = {
        "Authorization": f"Bearer {provisioned_tenants['tenant_a']['token']}",
        "X-Tenant-Slug": "tenanta"
    }

    # Create subscription
    create_resp = client.post("/api/v1/app/webhooks", json={
        "name": "Retry Test",
        "target_url": "https://example.com/webhook",
        "events": ["ping"]
    }, headers=headers_a)
    sub_data = create_resp.json()["data"]
    sub_id = uuid.UUID(sub_data["id"])

    # Manually insert a pending WebhookDelivery
    delivery = WebhookDelivery(
        tenant_id=provisioned_tenants["tenant_a"]["id"],
        webhook_subscription_id=sub_id,
        event_type="ping",
        payload={"msg": "hello retry"},
        status="pending",
        attempt_count=0
    )
    db_session.add(delivery)
    db_session.commit()

    # Run outbox worker with httpx post failing
    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")):
        worker = OutboxWorker(max_attempts=3)
        worker.run(once=True)

    db_session.commit()
    # Check that status became failed and next_retry_at is scheduled
    db_session.refresh(delivery)
    assert delivery.status == "failed"
    assert delivery.attempt_count == 1
    assert delivery.next_retry_at is not None
    assert delivery.last_error == "Connection refused"

def test_webhook_outbox_integration(client, provisioned_tenants, db_session):
    headers_a = {
        "Authorization": f"Bearer {provisioned_tenants['tenant_a']['token']}",
        "X-Tenant-Slug": "tenanta"
    }

    # Create subscription
    create_resp = client.post("/api/v1/app/webhooks", json={
        "name": "Integration Test",
        "target_url": "https://example.com/webhook-integration",
        "events": ["custom.event"]
    }, headers=headers_a)
    sub_data = create_resp.json()["data"]
    sub_id = uuid.UUID(sub_data["id"])

    # Manually insert OutboxEvent
    event = OutboxEvent(
        tenant_id=provisioned_tenants["tenant_a"]["id"],
        event_key="custom.event",
        payload={"msg": "test integration payload"},
        status="pending"
    )
    db_session.add(event)
    db_session.commit()

    # Step 1: Run outbox worker. It should process the OutboxEvent and generate a WebhookDelivery record.
    worker = OutboxWorker()
    worker.run(once=True)

    db_session.commit()
    db_session.refresh(event)
    assert event.status == "processed"

    # Verify WebhookDelivery was created
    delivery = db_session.query(WebhookDelivery).filter(
        WebhookDelivery.webhook_subscription_id == sub_id
    ).first()
    assert delivery is not None
    assert delivery.status == "pending"
    assert delivery.event_type == "custom.event"
    assert delivery.payload == {"msg": "test integration payload"}

    # Step 2: Run worker again. This iteration will pick up the WebhookDelivery and post it.
    original_post = httpx.Client.post
    mock_calls = []

    def side_effect_post(self, url, *args, **kwargs):
        if "example.com" in str(url):
            mock_calls.append((str(url), kwargs))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            return mock_resp
        return original_post(self, url, *args, **kwargs)

    with patch("httpx.Client.post", side_effect=side_effect_post, autospec=True):
        worker.run(once=True)

    db_session.commit()
    db_session.refresh(delivery)
    assert delivery.status == "delivered"
    assert len(mock_calls) == 1
