import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.exceptions import register_exception_handlers
from dymo_saas_core.core.permissions import (
    require_authenticated_user,
    require_super_admin,
    require_tenant_member,
    require_role,
    require_any_role,
    require_any_permission,
    require_all_permissions,
    require_active_subscription,
    require_feature_access,
    require_usage_limit
)
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.models.models import (
    Tenant, TenantUser, TenantRole, TenantPermission,
    Subscription, Plan, PlanFeature, PlanLimit, UsageCounter, PlatformAdmin,
    tenant_user_roles, tenant_role_permissions
)
from dymo_saas_core.core.security import hash_password, create_access_token

# Define local test app
test_app = FastAPI()
register_exception_handlers(test_app)

@test_app.get("/test-authenticated")
def route_authenticated_endpoint(user = Depends(require_authenticated_user)):
    return success_response({"user_id": str(user.id)})

@test_app.get("/test-super-admin")
def route_super_admin_endpoint(admin = Depends(require_super_admin)):
    return success_response({"admin_id": str(admin.id)})

@test_app.get("/test-tenant-member")
def route_tenant_member_endpoint(user = Depends(require_tenant_member)):
    return success_response({"user_id": str(user.id)})

@test_app.get("/test-role")
def route_role_endpoint(user = Depends(require_role("admin"))):
    return success_response({"user_id": str(user.id)})

@test_app.get("/test-any-role")
def route_any_role_endpoint(user = Depends(require_any_role(["admin", "editor"]))):
    return success_response({"user_id": str(user.id)})

@test_app.get("/test-any-permission")
def route_any_permission_endpoint(user = Depends(require_any_permission(["billing.manage", "users.view"]))):
    return success_response({"user_id": str(user.id)})

@test_app.get("/test-all-permissions")
def route_all_permissions_endpoint(user = Depends(require_all_permissions(["billing.manage", "users.view"]))):
    return success_response({"user_id": str(user.id)})

@test_app.get("/test-active-subscription")
def route_active_subscription_endpoint(sub = Depends(require_active_subscription())):
    return success_response({"subscription_id": str(sub.id)})

@test_app.get("/test-feature-access")
def route_feature_access_endpoint(feature = Depends(require_feature_access("invoicing"))):
    return success_response({"feature_key": feature.feature_key})

@test_app.get("/test-usage-limit")
def route_usage_limit_endpoint(limit = Depends(require_usage_limit("users_count"))):
    return success_response({"metric_key": limit.metric_key if limit else None})


@pytest.fixture
def test_client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    test_app.dependency_overrides[get_db] = override_get_db
    with TestClient(test_app) as client:
        yield client
    test_app.dependency_overrides.clear()


@pytest.fixture
def seed_test_env(db_session):
    # Create Tenant
    tenant = Tenant(
        name="Access Control Org",
        slug="access-org",
        status="active",
        owner_email="owner@access.com",
    )
    db_session.add(tenant)
    db_session.flush()

    # Create Owner User
    owner_user = TenantUser(
        tenant_id=tenant.id,
        email="owner@access.com",
        password_hash=hash_password("OwnerPassword123!"),
        status="active"
    )
    db_session.add(owner_user)

    # Create Regular User
    reg_user = TenantUser(
        tenant_id=tenant.id,
        email="user@access.com",
        password_hash=hash_password("UserPassword123!"),
        status="active"
    )
    db_session.add(reg_user)
    db_session.flush()

    # Roles and permissions setup
    owner_role = TenantRole(tenant_id=tenant.id, name="owner", description="Owner")
    admin_role = TenantRole(tenant_id=tenant.id, name="admin", description="Admin")
    editor_role = TenantRole(tenant_id=tenant.id, name="editor", description="Editor")
    db_session.add_all([owner_role, admin_role, editor_role])
    db_session.flush()

    # Link owner_user to owner_role
    db_session.execute(tenant_user_roles.insert().values(user_id=owner_user.id, role_id=owner_role.id))

    # Link reg_user to editor_role
    db_session.execute(tenant_user_roles.insert().values(user_id=reg_user.id, role_id=editor_role.id))

    # Seed Permissions
    perm_billing = TenantPermission(code="billing.manage", name="Billing Manage", description="")
    perm_users = TenantPermission(code="users.view", name="Users View", description="")
    db_session.add_all([perm_billing, perm_users])
    db_session.flush()

    # Link permissions to editor role
    db_session.execute(tenant_role_permissions.insert().values(role_id=editor_role.id, permission_id=perm_billing.id))

    # Create Platform Admin
    p_admin = PlatformAdmin(
        email="superadmin@dymo.com",
        password_hash=hash_password("SuperAdmin123!"),
        is_active=True
    )
    db_session.add(p_admin)
    db_session.flush()

    # Create Plan and Features
    plan = Plan(
        name="Pro Plan",
        slug="pro",
        status="active",
        trial_enabled=False,
    )
    db_session.add(plan)
    db_session.flush()

    feature = PlanFeature(
        plan_id=plan.id,
        feature_key="invoicing",
        name="Invoicing Feature"
    )
    db_session.add(feature)

    limit = PlanLimit(
        plan_id=plan.id,
        metric_key="users_count",
        limit_value=5,
        overage_allowed=False
    )
    db_session.add(limit)
    db_session.flush()

    # Create Subscription
    subscription = Subscription(
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="active",
        billing_cycle="monthly",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db_session.add(subscription)
    db_session.commit()

    return {
        "tenant": tenant,
        "owner_user": owner_user,
        "reg_user": reg_user,
        "platform_admin": p_admin,
        "plan": plan,
        "subscription": subscription,
        "limit": limit
    }


def test_authenticated_user_guard(test_client, seed_test_env):
    user = seed_test_env["reg_user"]
    tenant = seed_test_env["tenant"]

    # Unauthenticated
    resp = test_client.get("/test-authenticated")
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "NOT_AUTHENTICATED"

    # Authenticated
    token = create_access_token(
        payload={"user_id": str(user.id), "tenant_id": str(tenant.id), "user_type": "tenant_user"}
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Slug": tenant.slug}
    resp = test_client.get("/test-authenticated", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["user_id"] == str(user.id)


def test_super_admin_guard(test_client, seed_test_env):
    user = seed_test_env["reg_user"]
    tenant = seed_test_env["tenant"]
    p_admin = seed_test_env["platform_admin"]

    # Normal user tries to access super admin route
    token = create_access_token(
        payload={"user_id": str(user.id), "tenant_id": str(tenant.id), "user_type": "tenant_user"}
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Slug": tenant.slug}
    resp = test_client.get("/test-super-admin", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "PLATFORM_ADMIN_REQUIRED"

    # Real platform admin
    admin_token = create_access_token(
        payload={"admin_id": str(p_admin.id), "user_type": "platform_admin"}
    )
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    resp = test_client.get("/test-super-admin", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["admin_id"] == str(p_admin.id)


def test_tenant_member_guard(test_client, seed_test_env, db_session):
    user = seed_test_env["reg_user"]
    tenant = seed_test_env["tenant"]

    token = create_access_token(
        payload={"user_id": str(user.id), "tenant_id": str(tenant.id), "user_type": "tenant_user"}
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Slug": tenant.slug}

    # Active Tenant
    resp = test_client.get("/test-tenant-member", headers=headers)
    assert resp.status_code == 200

    # Suspended Tenant
    tenant.status = "suspended"
    db_session.commit()

    resp = test_client.get("/test-tenant-member", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "TENANT_SUSPENDED"


def test_role_guards(test_client, seed_test_env, db_session):
    # Regular user has 'editor' role, owner user has 'owner' role
    reg_user = seed_test_env["reg_user"]
    owner_user = seed_test_env["owner_user"]
    tenant = seed_test_env["tenant"]

    # 1. Require 'admin' role on reg_user (fails)
    token_reg = create_access_token(
        payload={"user_id": str(reg_user.id), "tenant_id": str(tenant.id), "user_type": "tenant_user"}
    )
    headers_reg = {"Authorization": f"Bearer {token_reg}", "X-Tenant-Slug": tenant.slug}
    resp = test_client.get("/test-role", headers=headers_reg)
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "ROLE_DENIED"

    # 2. Owner user accesses require 'admin' role (owner bypasses/has super rights)
    token_owner = create_access_token(
        payload={"user_id": str(owner_user.id), "tenant_id": str(tenant.id), "user_type": "tenant_user"}
    )
    headers_owner = {"Authorization": f"Bearer {token_owner}", "X-Tenant-Slug": tenant.slug}
    resp = test_client.get("/test-role", headers=headers_owner)
    assert resp.status_code == 200

    # 3. Require 'any' role (editor role is in [admin, editor])
    resp = test_client.get("/test-any-role", headers=headers_reg)
    assert resp.status_code == 200


def test_permission_guards(test_client, seed_test_env, db_session):
    # Editor role has only 'billing.manage' permission.
    reg_user = seed_test_env["reg_user"]
    tenant = seed_test_env["tenant"]

    token = create_access_token(
        payload={"user_id": str(reg_user.id), "tenant_id": str(tenant.id), "user_type": "tenant_user"}
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Slug": tenant.slug}

    # 1. require_any_permission ("billing.manage", "users.view") -> editor has billing.manage, so succeeds.
    resp = test_client.get("/test-any-permission", headers=headers)
    assert resp.status_code == 200

    # 2. require_all_permissions ("billing.manage", "users.view") -> editor lacks users.view, so fails.
    resp = test_client.get("/test-all-permissions", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "PERMISSION_DENIED"


def test_active_subscription_guard(test_client, seed_test_env, db_session):
    reg_user = seed_test_env["reg_user"]
    tenant = seed_test_env["tenant"]
    sub = seed_test_env["subscription"]

    token = create_access_token(
        payload={"user_id": str(reg_user.id), "tenant_id": str(tenant.id), "user_type": "tenant_user"}
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Slug": tenant.slug}

    # Subscription is active
    resp = test_client.get("/test-active-subscription", headers=headers)
    assert resp.status_code == 200

    # Update subscription status to expired
    sub.status = "expired"
    db_session.commit()

    resp = test_client.get("/test-active-subscription", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "NO_ACTIVE_SUBSCRIPTION"


def test_feature_access_guard(test_client, seed_test_env, db_session):
    reg_user = seed_test_env["reg_user"]
    tenant = seed_test_env["tenant"]

    token = create_access_token(
        payload={"user_id": str(reg_user.id), "tenant_id": str(tenant.id), "user_type": "tenant_user"}
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Slug": tenant.slug}

    # Has "invoicing" feature
    resp = test_client.get("/test-feature-access", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["feature_key"] == "invoicing"


def test_usage_limit_guard(test_client, seed_test_env, db_session):
    reg_user = seed_test_env["reg_user"]
    tenant = seed_test_env["tenant"]

    token = create_access_token(
        payload={"user_id": str(reg_user.id), "tenant_id": str(tenant.id), "user_type": "tenant_user"}
    )
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-Slug": tenant.slug}

    # No usage counter exists, so current value is 0. limit is 5.
    resp = test_client.get("/test-usage-limit", headers=headers)
    assert resp.status_code == 200

    # Add usage counter under limit (4)
    counter = UsageCounter(
        tenant_id=tenant.id,
        metric_key="users_count",
        current_value=4,
        period_start=datetime.now(timezone.utc) - timedelta(days=1),
        period_end=datetime.now(timezone.utc) + timedelta(days=29)
    )
    db_session.add(counter)
    db_session.commit()

    resp = test_client.get("/test-usage-limit", headers=headers)
    assert resp.status_code == 200

    # Add usage counter exceeding limit (5)
    counter.current_value = 5
    db_session.commit()

    resp = test_client.get("/test-usage-limit", headers=headers)
    assert resp.status_code == 402
    assert resp.json()["error_code"] == "QUOTA_EXCEEDED"
