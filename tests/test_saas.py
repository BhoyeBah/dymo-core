import pytest
from dymo_saas_core.core.security import hash_password
from dymo_saas_core.models.models import PlatformAdmin, Plan, PlanPrice, PlanLimit, PlanFeature, PlanModule, Tenant, TenantUser, TenantRole, Subscription, TenantPermission, TenantModule
from dymo_saas_core.core.module_registry import sync_modules_to_database
from dymo_saas_core.modules.cash_register_simple.models import CashRegisterSale

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

def test_platform_admin_login(client):
    # Authenticate Platform Admin
    response = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data["data"]
    assert "refresh_token" in data["data"]

def test_tenant_provisioning_and_app_auth(client, db_session):
    # 1. Login as Platform Admin
    login_resp = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    token = login_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Provision Tenant
    tenant_payload = {
        "name": "Acme Inc",
        "slug": "acme",
        "owner_email": "owner@acme.com",
        "owner_phone": "+33612345678",
        "country": "France",
        "currency": "EUR",
        "timezone": "Europe/Paris",
        "language": "fr"
    }
    prov_resp = client.post("/api/v1/platform/tenants", json=tenant_payload, headers=headers)
    assert prov_resp.status_code == 200
    tenant_data = prov_resp.json()["data"]
    assert tenant_data["slug"] == "acme"
    
    # 3. Authenticate as Tenant Owner
    tenant_login_resp = client.post("/api/v1/app/auth/login", json={
        "email": "owner@acme.com",
        "password": "ChangeMe123!"  # Seeded temp password
    }, headers={
        "X-Tenant-Slug": "acme"
    })
    assert tenant_login_resp.status_code == 200
    tenant_token = tenant_login_resp.json()["data"]["access_token"]
    
    # 4. Check user list on Tenant App
    users_resp = client.get("/api/v1/app/users", headers={
        "Authorization": f"Bearer {tenant_token}",
        "X-Tenant-Slug": "acme"
    })
    assert users_resp.status_code == 200
    users = users_resp.json()["data"]
    assert len(users) == 1
    assert users[0]["email"] == "owner@acme.com"

def test_module_gating(client, db_session):
    # 1. Login as Platform Admin and provision tenant
    login_resp = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    token = login_resp.json()["data"]["access_token"]
    
    tenant_payload = {
        "name": "Acme Inc",
        "slug": "acme",
        "owner_email": "owner@acme.com"
    }
    client.post("/api/v1/platform/tenants", json=tenant_payload, headers={"Authorization": f"Bearer {token}"})
    
    # Associate tenant with standard subscription so cash_register_simple module is enabled
    from datetime import datetime, timezone, timedelta
    from dymo_saas_core.models.models import Subscription
    tenant = db_session.query(Tenant).filter(Tenant.slug == "acme").first()
    plan = db_session.query(Plan).filter(Plan.slug == "standard").first()
    
    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db_session.add(sub)
    db_session.commit()

    owner = db_session.query(TenantUser).filter(
        TenantUser.tenant_id == tenant.id,
        TenantUser.email == "owner@acme.com"
    ).first()
    db_session.add(CashRegisterSale(
        tenant_id=tenant.id,
        created_by_user_id=owner.id,
        amount=20.0,
        amount_received=20.0,
        change_amount=0.0,
        payment_method="cash",
        status="completed"
    ))
    db_session.commit()

    # 2. Login as Tenant Owner
    tenant_login_resp = client.post("/api/v1/app/auth/login", json={
        "email": "owner@acme.com",
        "password": "ChangeMe123!"
    }, headers={"X-Tenant-Slug": "acme"})
    tenant_token = tenant_login_resp.json()["data"]["access_token"]
    
    # 3. Call simple cash register endpoint (should succeed since cash_register_simple is in standard plan)
    invoices_resp = client.get("/api/v1/app/cash-register/sales", headers={
        "Authorization": f"Bearer {tenant_token}",
        "X-Tenant-Slug": "acme"
    })
    assert invoices_resp.status_code == 200
    assert len(invoices_resp.json()) == 1
    assert invoices_resp.json()[0]["tenant_id"] == str(tenant.id)

    # 4. Manually disable the module for this tenant (Simulate tenant modular override)
    from dymo_saas_core.models.models import TenantModule
    tm = TenantModule(tenant_id=tenant.id, module_key="cash_register_simple", is_enabled=False)
    db_session.add(tm)
    db_session.commit()
    
    # 5. Access the invoicing module again, it should fail now!
    failed_resp = client.get("/api/v1/app/cash-register/sales", headers={
        "Authorization": f"Bearer {tenant_token}",
        "X-Tenant-Slug": "acme"
    })
    assert failed_resp.status_code == 403
    assert "not enabled" in failed_resp.json()["message"]


def test_setup_database_safety_check():
    import pytest
    from dymo_saas_core.core.config import settings
    # Backup original values
    original_env = settings.ENVIRONMENT
    original_url = settings.DATABASE_URL
    
    try:
        # Simulate non-test environment and URL without "test"
        settings.ENVIRONMENT = "production"
        settings.DATABASE_URL = "postgresql://postgres:pass@localhost:5432/production_db"
        
        from conftest import setup_database
        # Directly invoke the generator fixture's underlying function
        generator = setup_database.__wrapped__()
        with pytest.raises(RuntimeError) as exc_info:
            next(generator)
        assert "CRITICAL SAFETY WARNING" in str(exc_info.value)
    finally:
        # Restore
        settings.ENVIRONMENT = original_env
        settings.DATABASE_URL = original_url


def test_logout_flows(client, db_session):
    # 1. Platform Logout
    login_resp = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    token_data = login_resp.json()["data"]
    admin_token = token_data["access_token"]
    admin_refresh = token_data["refresh_token"]
    
    logout_resp = client.post(
        f"/api/v1/platform/auth/logout?refresh_token={admin_refresh}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert logout_resp.status_code == 200
    assert "Logged out successfully" in logout_resp.json()["message"]
    
    # Verify token is indeed revoked
    from dymo_saas_core.models.models import PlatformRefreshToken
    from dymo_saas_core.core.security import hash_token
    r_hash = hash_token(admin_refresh)
    token_rec = db_session.query(PlatformRefreshToken).filter(PlatformRefreshToken.token_hash == r_hash).first()
    assert token_rec.is_revoked is True

    # 2. Tenant Logout
    # Provision tenant
    tenant_payload = {
        "name": "Beta Corp",
        "slug": "beta",
        "owner_email": "owner@beta.com"
    }
    client.post("/api/v1/platform/tenants", json=tenant_payload, headers={"Authorization": f"Bearer {admin_token}"})
    
    tenant_login_resp = client.post("/api/v1/app/auth/login", json={
        "email": "owner@beta.com",
        "password": "ChangeMe123!"
    }, headers={"X-Tenant-Slug": "beta"})
    tenant_tokens = tenant_login_resp.json()["data"]
    t_access = tenant_tokens["access_token"]
    t_refresh = tenant_tokens["refresh_token"]
    
    t_logout_resp = client.post(
        f"/api/v1/app/auth/logout?refresh_token={t_refresh}",
        headers={
            "Authorization": f"Bearer {t_access}",
            "X-Tenant-Slug": "beta"
        }
    )
    assert t_logout_resp.status_code == 200
    
    from dymo_saas_core.models.models import TenantRefreshToken
    t_hash = hash_token(t_refresh)
    t_rec = db_session.query(TenantRefreshToken).filter(TenantRefreshToken.token_hash == t_hash).first()
    assert t_rec.is_revoked is True


def test_subscription_cancellation(client, db_session):
    # 1. Authenticate platform and provision tenant
    login_resp = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    admin_token = login_resp.json()["data"]["access_token"]
    
    tenant_payload = {
        "name": "Cancel Corp",
        "slug": "cancelcorp",
        "owner_email": "owner@cancel.com"
    }
    client.post("/api/v1/platform/tenants", json=tenant_payload, headers={"Authorization": f"Bearer {admin_token}"})
    
    # Login as tenant owner
    t_login_resp = client.post("/api/v1/app/auth/login", json={
        "email": "owner@cancel.com",
        "password": "ChangeMe123!"
    }, headers={"X-Tenant-Slug": "cancelcorp"})
    t_access = t_login_resp.json()["data"]["access_token"]
    
    # 2. Add subscription so we can cancel it
    from dymo_saas_core.models.models import Subscription, Plan, Tenant
    tenant = db_session.query(Tenant).filter(Tenant.slug == "cancelcorp").first()
    plan = db_session.query(Plan).filter(Plan.slug == "standard").first()
    from datetime import datetime, timezone, timedelta
    
    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db_session.add(sub)
    db_session.commit()
    
    # 3. Call cancel endpoint
    cancel_resp = client.post(
        "/api/v1/app/billing/subscription/cancel",
        headers={
            "Authorization": f"Bearer {t_access}",
            "X-Tenant-Slug": "cancelcorp"
        }
    )
    assert cancel_resp.status_code == 200
    assert "cancel at period end" in cancel_resp.json()["message"]
    
    # Verify in DB
    db_session.refresh(sub)
    assert sub.cancel_at_period_end is True


def test_rbac_forbidden(client, db_session):
    # 1. Authenticate platform and provision tenant
    login_resp = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    admin_token = login_resp.json()["data"]["access_token"]
    
    tenant_payload = {
        "name": "Rbac Corp",
        "slug": "rbaccorp",
        "owner_email": "owner@rbac.com"
    }
    client.post("/api/v1/platform/tenants", json=tenant_payload, headers={"Authorization": f"Bearer {admin_token}"})
    
    # 2. Create standard user without permissions
    from dymo_saas_core.models.models import TenantUser, Tenant, TenantRole
    tenant = db_session.query(Tenant).filter(Tenant.slug == "rbaccorp").first()
    
    # Assign standard role without billing or admin permissions
    std_role = TenantRole(
        tenant_id=tenant.id,
        name="limited",
        description="Limited role"
    )
    db_session.add(std_role)
    db_session.flush()
    
    from dymo_saas_core.core.security import hash_password
    limited_user = TenantUser(
        tenant_id=tenant.id,
        email="limited@rbac.com",
        first_name="Limited",
        last_name="User",
        password_hash=hash_password("Password123!"),
        status="active"
    )
    db_session.add(limited_user)
    db_session.flush()
    limited_user.roles.append(std_role)
    db_session.commit()
    
    # Login as standard user
    user_login_resp = client.post("/api/v1/app/auth/login", json={
        "email": "limited@rbac.com",
        "password": "Password123!"
    }, headers={"X-Tenant-Slug": "rbaccorp"})
    user_access = user_login_resp.json()["data"]["access_token"]
    
    # Try to access users list (requires 'users.manage' permission)
    users_resp = client.get(
        "/api/v1/app/users",
        headers={
            "Authorization": f"Bearer {user_access}",
            "X-Tenant-Slug": "rbaccorp"
        }
    )
    assert users_resp.status_code == 403
    assert "Missing required permission" in users_resp.json()["message"]


def test_idempotency(client, db_session):
    # 1. Authenticate platform and provision tenant
    login_resp = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    admin_token = login_resp.json()["data"]["access_token"]
    
    tenant_payload = {
        "name": "Idemp Corp",
        "slug": "idemp",
        "owner_email": "owner@idemp.com"
    }
    client.post("/api/v1/platform/tenants", json=tenant_payload, headers={"Authorization": f"Bearer {admin_token}"})
    
    # Login as tenant owner
    t_login_resp = client.post("/api/v1/app/auth/login", json={
        "email": "owner@idemp.com",
        "password": "ChangeMe123!"
    }, headers={"X-Tenant-Slug": "idemp"})
    t_access = t_login_resp.json()["data"]["access_token"]
    
    from dymo_saas_core.models.models import TenantRole, Tenant
    tenant = db_session.query(Tenant).filter(Tenant.slug == "idemp").first()
    role = db_session.query(TenantRole).filter(TenantRole.tenant_id == tenant.id, TenantRole.name == "admin").first()
    
    # Invite a user with an Idempotency-Key
    invite_payload = {
        "email": "newuser@idemp.com",
        "role_id": str(role.id)
    }
    headers = {
        "Authorization": f"Bearer {t_access}",
        "X-Tenant-Slug": "idemp",
        "Idempotency-Key": "unique-invite-key-123456"
    }
    
    # First request
    resp1 = client.post("/api/v1/app/invitations", json=invite_payload, headers=headers)
    assert resp1.status_code == 200
    resp1_data = resp1.json()
    
    # Second request with same Idempotency-Key and SAME payload -> Should return cached success response
    resp2 = client.post("/api/v1/app/invitations", json=invite_payload, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json() == resp1_data
    
    # Third request with same Idempotency-Key but DIFFERENT payload -> Should return conflict (409)
    different_payload = {
        "email": "otheruser@idemp.com",
        "role_id": str(role.id)
    }
    resp3 = client.post("/api/v1/app/invitations", json=different_payload, headers=headers)
    assert resp3.status_code == 409
    assert "different request payload" in resp3.json()["message"]


def test_quotas(client, db_session):
    from dymo_saas_core.core.quota import check_limit, increment_usage
    from dymo_saas_core.models.models import Subscription, Plan, Tenant, PlanLimit
    import pytest
    from dymo_saas_core.core.exceptions import QuotaExceededException

    # 1. Setup tenant
    tenant = Tenant(name="Quota Corp", slug="quotacorp", status="active", owner_email="owner@quota.com")
    db_session.add(tenant)
    db_session.flush()
    
    plan = db_session.query(Plan).filter(Plan.slug == "standard").first()
    
    from datetime import datetime, timezone, timedelta
    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db_session.add(sub)
    db_session.flush()
    
    # Overwrite metric limit in database specifically for test: max_documents = 2, overage NOT allowed
    limit = db_session.query(PlanLimit).filter(
        PlanLimit.plan_id == plan.id,
        PlanLimit.metric_key == "max_documents"
    ).first()
    
    if not limit:
        limit = PlanLimit(
            plan_id=plan.id,
            metric_key="max_documents",
            limit_value=2,
            period="monthly",
            overage_allowed=False
        )
        db_session.add(limit)
    else:
        limit.limit_value = 2
        limit.overage_allowed = False
    db_session.commit()
    
    # Check limit before usage
    assert check_limit(db_session, tenant.id, "max_documents", 1) is True
    
    # Increment usage by 1
    increment_usage(db_session, tenant.id, "max_documents", 1)
    assert check_limit(db_session, tenant.id, "max_documents", 1) is True
    
    # Increment usage by 1 (reaches 2)
    increment_usage(db_session, tenant.id, "max_documents", 1)
    
    # Next request should be blocked
    with pytest.raises(QuotaExceededException) as exc_info:
        check_limit(db_session, tenant.id, "max_documents", 1)
    assert "Quota exceeded" in str(exc_info.value)


def test_invitation_flow_with_audit(client, db_session):
    # 1. Authenticate platform and provision tenant
    login_resp = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    admin_token = login_resp.json()["data"]["access_token"]
    
    tenant_payload = {
        "name": "Audit Corp",
        "slug": "auditcorp",
        "owner_email": "owner@audit.com"
    }
    client.post("/api/v1/platform/tenants", json=tenant_payload, headers={"Authorization": f"Bearer {admin_token}"})
    
    # Login as tenant owner
    t_login_resp = client.post("/api/v1/app/auth/login", json={
        "email": "owner@audit.com",
        "password": "ChangeMe123!"
    }, headers={"X-Tenant-Slug": "auditcorp"})
    t_access = t_login_resp.json()["data"]["access_token"]
    
    from dymo_saas_core.models.models import TenantRole, Tenant
    tenant = db_session.query(Tenant).filter(Tenant.slug == "auditcorp").first()
    role = db_session.query(TenantRole).filter(TenantRole.tenant_id == tenant.id, TenantRole.name == "admin").first()
    
    # Invite a user
    invite_resp = client.post("/api/v1/app/invitations", json={
        "email": "invitee@audit.com",
        "role_id": str(role.id)
    }, headers={
        "Authorization": f"Bearer {t_access}",
        "X-Tenant-Slug": "auditcorp"
    })
    token = invite_resp.json()["data"]["token"]
    
    # 2. Accept invitation
    accept_payload = {
        "token": token,
        "password": "SecurePassword123!",
        "first_name": "Invited",
        "last_name": "User"
    }
    accept_resp = client.post("/api/v1/app/invitations/accept", json=accept_payload)
    assert accept_resp.status_code == 200
    
    # 3. Verify that a TenantAuditLog entry was written
    from dymo_saas_core.models.models import TenantAuditLog
    audit_rec = db_session.query(TenantAuditLog).filter(
        TenantAuditLog.tenant_id == tenant.id,
        TenantAuditLog.action == "tenant.invitation_accepted"
    ).first()
    assert audit_rec is not None
    assert audit_rec.payload["email"] == "invitee@audit.com"


def test_module_permissions_and_isolation(client, db_session):
    # 1. Login as Platform Admin and provision two tenants
    login_resp = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    admin_token = login_resp.json()["data"]["access_token"]
    
    # Tenant A
    client.post("/api/v1/platform/tenants", json={
        "name": "Tenant A",
        "slug": "tenanta",
        "owner_email": "owner@tenanta.com"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    
    # Tenant B
    client.post("/api/v1/platform/tenants", json={
        "name": "Tenant B",
        "slug": "tenantb",
        "owner_email": "owner@tenantb.com"
    }, headers={"Authorization": f"Bearer {admin_token}"})
    
    # Fetch database objects
    from datetime import datetime, timezone, timedelta
    from dymo_saas_core.models.models import Tenant, Plan, Subscription, TenantUser, TenantRole, TenantPermission
    tenant_a = db_session.query(Tenant).filter(Tenant.slug == "tenanta").first()
    tenant_b = db_session.query(Tenant).filter(Tenant.slug == "tenantb").first()
    plan = db_session.query(Plan).filter(Plan.slug == "standard").first()
    
    # Enable cash_register_simple for Tenant A (using subscription)
    sub_a = Subscription(
        tenant_id=tenant_a.id,
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30)
    )
    # Enable cash_register_simple for Tenant B (using subscription)
    sub_b = Subscription(
        tenant_id=tenant_b.id,
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db_session.add_all([sub_a, sub_b])
    db_session.commit()

    owner_a = db_session.query(TenantUser).filter(
        TenantUser.tenant_id == tenant_a.id,
        TenantUser.email == "owner@tenanta.com"
    ).first()
    owner_b = db_session.query(TenantUser).filter(
        TenantUser.tenant_id == tenant_b.id,
        TenantUser.email == "owner@tenantb.com"
    ).first()
    db_session.add_all([
        CashRegisterSale(
            tenant_id=tenant_a.id,
            created_by_user_id=owner_a.id,
            amount=15.0,
            amount_received=15.0,
            change_amount=0.0,
            payment_method="cash",
            status="completed"
        ),
        CashRegisterSale(
            tenant_id=tenant_b.id,
            created_by_user_id=owner_b.id,
            amount=30.0,
            amount_received=30.0,
            change_amount=0.0,
            payment_method="cash",
            status="completed"
        )
    ])
    db_session.commit()
    
    # Create standard (non-owner) user for Tenant A
    staff_role = TenantRole(
        tenant_id=tenant_a.id,
        name="staff",
        description="Tenant A Staff"
    )
    db_session.add(staff_role)
    db_session.flush()
    
    from dymo_saas_core.core.security import hash_password
    staff_user = TenantUser(
        tenant_id=tenant_a.id,
        email="staff@tenanta.com",
        first_name="Staff",
        last_name="User",
        password_hash=hash_password("Password123!"),
        status="active"
    )
    db_session.add(staff_user)
    db_session.flush()
    staff_user.roles.append(staff_role)
    db_session.commit()
    
    # Login as Staff User (Tenant A)
    staff_login_resp = client.post("/api/v1/app/auth/login", json={
        "email": "staff@tenanta.com",
        "password": "Password123!"
    }, headers={"X-Tenant-Slug": "tenanta"})
    staff_token = staff_login_resp.json()["data"]["access_token"]
    
    # 2. Access module route WITHOUT permission -> should be 403 Forbidden
    invoices_resp = client.get("/api/v1/app/cash-register/sales", headers={
        "Authorization": f"Bearer {staff_token}",
        "X-Tenant-Slug": "tenanta"
    })
    assert invoices_resp.status_code == 403
    assert "Missing required permission" in invoices_resp.json()["message"]
    
    # Link permission 'cash_register_simple.sales.view' to Tenant A staff role
    perm = db_session.query(TenantPermission).filter(TenantPermission.code == "cash_register_simple.sales.view").first()
    assert perm is not None
    staff_role.permissions.append(perm)
    db_session.commit()
    from dymo_saas_core.core.cache import cache_service
    cache_service.flush()
    
    # 3. Access module route WITH permission -> should be 200 OK
    invoices_resp2 = client.get("/api/v1/app/cash-register/sales", headers={
        "Authorization": f"Bearer {staff_token}",
        "X-Tenant-Slug": "tenanta"
    })
    assert invoices_resp2.status_code == 200
    assert invoices_resp2.json()[0]["tenant_id"] == str(tenant_a.id)
    
    # 4. Access module route with module disabled -> should be 403 Forbidden
    from dymo_saas_core.models.models import TenantModule
    tm = TenantModule(tenant_id=tenant_a.id, module_key="cash_register_simple", is_enabled=False)
    db_session.add(tm)
    db_session.commit()
    
    invoices_resp3 = client.get("/api/v1/app/cash-register/sales", headers={
        "Authorization": f"Bearer {staff_token}",
        "X-Tenant-Slug": "tenanta"
    })
    assert invoices_resp3.status_code == 403
    assert "not enabled" in invoices_resp3.json()["message"]
    
    # 5. Cross-tenant isolation check: Login as Tenant B Owner
    t_login_b = client.post("/api/v1/app/auth/login", json={
        "email": "owner@tenantb.com",
        "password": "ChangeMe123!"
    }, headers={"X-Tenant-Slug": "tenantb"})
    token_b = t_login_b.json()["data"]["access_token"]
    
    # Call invoices endpoint using Tenant B's token. 
    # It must return Tenant B's tenant_id, even if headers are manipulated, because tenant context is derived from JWT
    invoices_resp_b = client.get("/api/v1/app/cash-register/sales", headers={
        "Authorization": f"Bearer {token_b}",
        "X-Tenant-Slug": "tenanta"  # Maliciously trying to request Tenant A's slug
    })
    assert invoices_resp_b.status_code == 200
    # Isolation: Must be Tenant B's id!
    assert invoices_resp_b.json()[0]["tenant_id"] == str(tenant_b.id)
    assert invoices_resp_b.json()[0]["tenant_id"] != str(tenant_a.id)


def test_seed_credentials_consistency(client, db_session):
    # Test that default seed credentials work for authentication
    
    # Platform Admin login
    admin_login = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    assert admin_login.status_code == 200
    assert "access_token" in admin_login.json()["data"]

    # Provision standard tenant
    token = admin_login.json()["data"]["access_token"]
    client.post("/api/v1/platform/tenants", json={
        "name": "Seed Check Corp",
        "slug": "seedcheck",
        "owner_email": "owner@seedcheck.com"
    }, headers={"Authorization": f"Bearer {token}"})

    # Tenant Owner login with the standard default seed password
    tenant_login = client.post("/api/v1/app/auth/login", json={
        "email": "owner@seedcheck.com",
        "password": "ChangeMe123!"
    }, headers={"X-Tenant-Slug": "seedcheck"})
    assert tenant_login.status_code == 200
    assert "access_token" in tenant_login.json()["data"]


def test_tenant_settings(client, db_session):
    # 1. Authenticate platform and provision tenant
    login_resp = client.post("/api/v1/platform/auth/login", json={
        "email": "admin@dymo.com",
        "password": "DymoAdmin2026!"
    })
    admin_token = login_resp.json()["data"]["access_token"]
    
    tenant_payload = {
        "name": "Settings Corp",
        "slug": "settingscorp",
        "owner_email": "owner@settings.com"
    }
    client.post("/api/v1/platform/tenants", json=tenant_payload, headers={"Authorization": f"Bearer {admin_token}"})
    
    # Login as tenant owner
    t_login_resp = client.post("/api/v1/app/auth/login", json={
        "email": "owner@settings.com",
        "password": "ChangeMe123!"
    }, headers={"X-Tenant-Slug": "settingscorp"})
    t_access = t_login_resp.json()["data"]["access_token"]
    
    headers = {
        "Authorization": f"Bearer {t_access}",
        "X-Tenant-Slug": "settingscorp"
    }
    
    # 2. Get settings (initially empty)
    get_resp = client.get("/api/v1/app/settings", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"] == []
    
    # 3. Create non-sensitive setting
    post_resp = client.post("/api/v1/app/settings", json={
        "key": "app_theme",
        "value": "dark"
    }, headers=headers)
    assert post_resp.status_code == 200
    assert post_resp.json()["data"]["key"] == "app_theme"
    assert post_resp.json()["data"]["value"] == "dark"
    assert post_resp.json()["data"]["is_encrypted"] is False
    
    # Verify in DB
    from dymo_saas_core.models.models import TenantSetting, Tenant
    tenant = db_session.query(Tenant).filter(Tenant.slug == "settingscorp").first()
    db_setting_theme = db_session.query(TenantSetting).filter(
        TenantSetting.tenant_id == tenant.id,
        TenantSetting.key == "app_theme"
    ).first()
    assert db_setting_theme is not None
    assert db_setting_theme.value == "dark"
    assert db_setting_theme.is_encrypted is False
    
    # 4. Create sensitive setting
    post_resp2 = client.post("/api/v1/app/settings", json={
        "key": "stripe_api_key",
        "value": "sk_test_512345"
    }, headers=headers)
    assert post_resp2.status_code == 200
    assert post_resp2.json()["data"]["key"] == "stripe_api_key"
    assert post_resp2.json()["data"]["value"] == "********"
    assert post_resp2.json()["data"]["is_encrypted"] is True
    
    # Verify in DB (should be encrypted, not plain text)
    db_setting_key = db_session.query(TenantSetting).filter(
        TenantSetting.tenant_id == tenant.id,
        TenantSetting.key == "stripe_api_key"
    ).first()
    assert db_setting_key is not None
    assert db_setting_key.value != "sk_test_512345"
    assert db_setting_key.is_encrypted is True
    
    # Verify decrypted service reading
    from dymo_saas_core.tenant_app.settings.service import get_decrypted_setting
    decrypted = get_decrypted_setting(db_session, tenant.id, "stripe_api_key")
    assert decrypted == "sk_test_512345"
    
    # 5. List settings (should return masked values)
    get_resp2 = client.get("/api/v1/app/settings", headers=headers)
    assert get_resp2.status_code == 200
    settings_list = get_resp2.json()["data"]
    assert len(settings_list) == 2
    
    theme_item = next(s for s in settings_list if s["key"] == "app_theme")
    stripe_item = next(s for s in settings_list if s["key"] == "stripe_api_key")
    assert theme_item["value"] == "dark"
    assert stripe_item["value"] == "********"
    
    # 6. Update sensitive setting with masked value -> should not modify secret
    post_resp3 = client.post("/api/v1/app/settings", json={
        "key": "stripe_api_key",
        "value": "********"
    }, headers=headers)
    assert post_resp3.status_code == 200
    
    # Verify DB value is unchanged
    db_session.expire_all()
    db_setting_key2 = db_session.query(TenantSetting).filter(
        TenantSetting.tenant_id == tenant.id,
        TenantSetting.key == "stripe_api_key"
    ).first()
    assert db_setting_key2.value == db_setting_key.value
    
    # 7. Update sensitive setting with a new value
    post_resp4 = client.post("/api/v1/app/settings", json={
        "key": "stripe_api_key",
        "value": "new_key_value"
    }, headers=headers)
    assert post_resp4.status_code == 200
    
    db_session.expire_all()
    decrypted2 = get_decrypted_setting(db_session, tenant.id, "stripe_api_key")
    assert decrypted2 == "new_key_value"
    
    # 8. Check RBAC permissions
    # Create standard user without permissions
    from dymo_saas_core.models.models import TenantUser, TenantRole
    std_role = TenantRole(
        tenant_id=tenant.id,
        name="std_limited",
        description="Limited role for settings testing"
    )
    db_session.add(std_role)
    db_session.flush()
    
    from dymo_saas_core.core.security import hash_password
    limited_user = TenantUser(
        tenant_id=tenant.id,
        email="limited_user@settings.com",
        first_name="Limited",
        last_name="User",
        password_hash=hash_password("Password123!"),
        status="active"
    )
    db_session.add(limited_user)
    db_session.flush()
    limited_user.roles.append(std_role)
    db_session.commit()
    
    # Login as limited user
    lim_login_resp = client.post("/api/v1/app/auth/login", json={
        "email": "limited_user@settings.com",
        "password": "Password123!"
    }, headers={"X-Tenant-Slug": "settingscorp"})
    lim_access = lim_login_resp.json()["data"]["access_token"]
    
    lim_headers = {
        "Authorization": f"Bearer {lim_access}",
        "X-Tenant-Slug": "settingscorp"
    }
    
    # Try to GET settings -> should be 403
    forbidden_get = client.get("/api/v1/app/settings", headers=lim_headers)
    assert forbidden_get.status_code == 403
    
    # Try to POST settings -> should be 403
    forbidden_post = client.post("/api/v1/app/settings", json={
        "key": "app_theme",
        "value": "light"
    }, headers=lim_headers)
    assert forbidden_post.status_code == 403


