import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    String, Boolean, DateTime, Integer, Numeric, JSON, ForeignKey, Table, Column, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dymo_saas_core.shared.base_model import BaseModel
from dymo_saas_core.shared.mixins import TenantMixin, SoftDeleteMixin
from dymo_saas_core.core.database import Base

# ==============================================================================
# PLATFORM SCHEMAS & TABLES
# ==============================================================================

# Platform Admin - Role link table (many-to-many)
platform_admin_roles = Table(
    "platform_admin_roles",
    Base.metadata,
    Column("admin_id", UUID(as_uuid=True), ForeignKey("platform_admins.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("platform_roles.id", ondelete="CASCADE"), primary_key=True),
)

# Platform Role - Permission link table (many-to-many)
platform_role_permissions = Table(
    "platform_role_permissions",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("platform_roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("platform_permissions.id", ondelete="CASCADE"), primary_key=True),
)

class PlatformAdmin(BaseModel):
    __tablename__ = "platform_admins"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    roles: Mapped[List["PlatformRole"]] = relationship(
        "PlatformRole", secondary=platform_admin_roles, back_populates="admins"
    )
    refresh_tokens: Mapped[List["PlatformRefreshToken"]] = relationship("PlatformRefreshToken", back_populates="admin", cascade="all, delete-orphan")


class PlatformRole(BaseModel):
    __tablename__ = "platform_roles"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    admins: Mapped[List[PlatformAdmin]] = relationship(
        PlatformAdmin, secondary=platform_admin_roles, back_populates="roles"
    )
    permissions: Mapped[List["PlatformPermission"]] = relationship(
        "PlatformPermission", secondary=platform_role_permissions, back_populates="roles"
    )


class PlatformPermission(BaseModel):
    __tablename__ = "platform_permissions"

    code: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    roles: Mapped[List[PlatformRole]] = relationship(
        PlatformRole, secondary=platform_role_permissions, back_populates="permissions"
    )


class PlatformRefreshToken(BaseModel):
    __tablename__ = "platform_refresh_tokens"

    admin_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_admins.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    admin: Mapped[PlatformAdmin] = relationship(PlatformAdmin, back_populates="refresh_tokens")


class PlatformAuditLog(BaseModel):
    __tablename__ = "platform_audit_logs"

    admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_admins.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_platform_audit_logs_created_at", "created_at"),
    )


class PlatformProviderConfig(BaseModel):
    __tablename__ = "core_provider_configs"

    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    environment: Mapped[str] = mapped_column(String(50), default="production", nullable=False)
    encrypted_credentials: Mapped[str] = mapped_column(String(10000), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supported_countries: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    supported_currencies: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    last_test_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_tested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_admins.id", ondelete="SET NULL"), nullable=True)
    updated_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_admins.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        Index("ix_core_provider_configs_provider_type", "provider_type"),
        Index("ix_core_provider_configs_is_active", "is_active"),
        Index("ix_core_provider_configs_is_default", "is_default"),
    )


class PlatformProviderLog(BaseModel):
    __tablename__ = "core_provider_logs"

    provider_config_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core_provider_configs.id", ondelete="CASCADE"), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    request_payload_masked: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    response_payload_masked: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_core_provider_logs_provider_config_id", "provider_config_id"),
        Index("ix_core_provider_logs_created_at", "created_at"),
    )


# ==============================================================================
# TENANT STRUCTS
# ==============================================================================

class Tenant(BaseModel):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending, trial, active, past_due, suspended, cancelled, deleted
    owner_email: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    country: Mapped[str] = mapped_column(String(100), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="EUR", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="fr", nullable=False)

    suspended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    profile: Mapped[Optional["TenantProfile"]] = relationship("TenantProfile", back_populates="tenant", uselist=False, cascade="all, delete-orphan")
    settings: Mapped[List["TenantSetting"]] = relationship("TenantSetting", back_populates="tenant", cascade="all, delete-orphan")
    status_history: Mapped[List["TenantStatusHistory"]] = relationship("TenantStatusHistory", back_populates="tenant", cascade="all, delete-orphan")
    users: Mapped[List["TenantUser"]] = relationship("TenantUser", back_populates="tenant", cascade="all, delete-orphan")
    api_keys: Mapped[List["TenantApiKey"]] = relationship("TenantApiKey", back_populates="tenant", cascade="all, delete-orphan")
    webhook_subscriptions: Mapped[List["WebhookSubscription"]] = relationship("WebhookSubscription", back_populates="tenant", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_tenants_status", "status"),
    )


class TenantProfile(BaseModel):
    __tablename__ = "tenant_profiles"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False)
    logo_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    primary_color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    secondary_color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    billing_details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant] = relationship(Tenant, back_populates="profile")


class TenantSetting(BaseModel, TenantMixin):
    __tablename__ = "tenant_settings"

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_encrypted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    tenant: Mapped[Tenant] = relationship(Tenant, back_populates="settings")


class TenantStatusHistory(BaseModel):
    __tablename__ = "tenant_status_history"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    old_status: Mapped[str] = mapped_column(String(50), nullable=False)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    changed_by_admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("platform_admins.id", ondelete="SET NULL"), nullable=True)

    tenant: Mapped[Tenant] = relationship(Tenant, back_populates="status_history")


# ==============================================================================
# TENANT USER SCHEMAS & RELATIONSHIPS
# ==============================================================================

# Tenant User - Role link table (many-to-many)
tenant_user_roles = Table(
    "tenant_user_roles",
    Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("tenant_users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("tenant_roles.id", ondelete="CASCADE"), primary_key=True),
)

# Tenant Role - Permission link table (many-to-many)
tenant_role_permissions = Table(
    "tenant_role_permissions",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("tenant_roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("tenant_permissions.id", ondelete="CASCADE"), primary_key=True),
)

class TenantUser(BaseModel, TenantMixin, SoftDeleteMixin):
    __tablename__ = "tenant_users"

    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active, inactive, invited, suspended, deleted

    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    phone_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped[Tenant] = relationship(Tenant, back_populates="users")
    roles: Mapped[List["TenantRole"]] = relationship("TenantRole", secondary=tenant_user_roles, back_populates="users")
    refresh_tokens: Mapped[List["TenantRefreshToken"]] = relationship("TenantRefreshToken", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_tenant_users_tenant_email"),
        Index("ix_tenant_users_status", "status"),
    )


class TenantRole(BaseModel, TenantMixin):
    __tablename__ = "tenant_roles"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    users: Mapped[List[TenantUser]] = relationship(TenantUser, secondary=tenant_user_roles, back_populates="roles")
    permissions: Mapped[List["TenantPermission"]] = relationship("TenantPermission", secondary=tenant_role_permissions, back_populates="roles")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tenant_roles_tenant_name"),
    )


class TenantPermission(BaseModel):
    __tablename__ = "tenant_permissions"

    code: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    module_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    roles: Mapped[List[TenantRole]] = relationship(TenantRole, secondary=tenant_role_permissions, back_populates="permissions")


class TenantInvitation(BaseModel, TenantMixin):
    __tablename__ = "tenant_invitations"

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenant_roles.id", ondelete="CASCADE"), nullable=False)
    invited_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("tenant_users.id", ondelete="SET NULL"), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending, accepted, expired, cancelled, revoked
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class TenantRefreshToken(BaseModel, TenantMixin):
    __tablename__ = "tenant_refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenant_users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[TenantUser] = relationship(TenantUser, back_populates="refresh_tokens")


class TenantAuditLog(BaseModel, TenantMixin):
    __tablename__ = "tenant_audit_logs"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("tenant_users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_tenant_audit_logs_tenant_id_created_at", "tenant_id", "created_at"),
    )


# ==============================================================================
# PLANS, SUBSCRIPTIONS, AND BILLING
# ==============================================================================

class Plan(BaseModel):
    __tablename__ = "plans"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active, inactive
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trial_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trial_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    prices: Mapped[List["PlanPrice"]] = relationship("PlanPrice", back_populates="plan", cascade="all, delete-orphan")
    limits: Mapped[List["PlanLimit"]] = relationship("PlanLimit", back_populates="plan", cascade="all, delete-orphan")
    features: Mapped[List["PlanFeature"]] = relationship("PlanFeature", back_populates="plan", cascade="all, delete-orphan")
    modules: Mapped[List["PlanModule"]] = relationship("PlanModule", back_populates="plan", cascade="all, delete-orphan")


class PlanPrice(BaseModel):
    __tablename__ = "plan_prices"

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(50), nullable=False)  # monthly, quarterly, yearly, custom
    currency: Mapped[str] = mapped_column(String(10), default="EUR", nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    setup_fee: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    plan: Mapped[Plan] = relationship(Plan, back_populates="prices")

    __table_args__ = (
        UniqueConstraint("plan_id", "billing_cycle", "currency", name="uq_plan_prices_plan_cycle_currency"),
    )


class PlanFeature(BaseModel):
    __tablename__ = "plan_features"

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    feature_key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    plan: Mapped[Plan] = relationship(Plan, back_populates="features")

    __table_args__ = (
        UniqueConstraint("plan_id", "feature_key", name="uq_plan_features_plan_feature"),
    )


class PlanLimit(BaseModel):
    __tablename__ = "plan_limits"

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    metric_key: Mapped[str] = mapped_column(String(100), nullable=False)
    limit_value: Mapped[int] = mapped_column(Integer, nullable=False)
    period: Mapped[str] = mapped_column(String(50), default="monthly", nullable=False)  # monthly, yearly, lifetime
    overage_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    overage_unit_price: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0, nullable=False)

    plan: Mapped[Plan] = relationship(Plan, back_populates="limits")

    __table_args__ = (
        UniqueConstraint("plan_id", "metric_key", name="uq_plan_limits_plan_metric"),
    )


class PlanModule(BaseModel):
    __tablename__ = "plan_modules"

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    module_key: Mapped[str] = mapped_column(String(100), nullable=False)

    plan: Mapped[Plan] = relationship(Plan, back_populates="modules")

    __table_args__ = (
        UniqueConstraint("plan_id", "module_key", name="uq_plan_modules_plan_module"),
    )


class Subscription(BaseModel, TenantMixin):
    __tablename__ = "subscriptions"

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="trialing", nullable=False)  # trialing, active, past_due, unpaid, cancelled, expired, suspended, incomplete
    billing_cycle: Mapped[str] = mapped_column(String(50), nullable=False)

    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    trial_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_billing_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    payment_provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_method_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_subscriptions_status", "status"),
        Index("ix_subscriptions_next_billing_date", "next_billing_date"),
    )


class SubscriptionEvent(BaseModel, TenantMixin):
    __tablename__ = "subscription_events"

    subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)  # created, upgraded, downgraded, cancelled, suspended, reactivated, payment_failed
    old_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="SET NULL"), nullable=True)
    new_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class SubscriptionScheduledChange(BaseModel, TenantMixin):
    __tablename__ = "subscription_scheduled_changes"

    subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)  # downgrade, cancel
    target_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="SET NULL"), nullable=True)
    execute_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_executed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class BillingInvoice(BaseModel, TenantMixin):
    __tablename__ = "billing_invoices"

    invoice_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    subscription_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)  # draft, open, paid, void, uncollectible, refunded
    currency: Mapped[str] = mapped_column(String(10), default="EUR", nullable=False)

    subtotal_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    tax_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    amount_paid: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    amount_due: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pdf_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stripe_invoice_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    items: Mapped[List["BillingInvoiceItem"]] = relationship("BillingInvoiceItem", back_populates="invoice", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_billing_invoices_status", "status"),
        Index("ix_billing_invoices_due_date", "due_date"),
    )


class BillingInvoiceItem(BaseModel, TenantMixin):
    __tablename__ = "billing_invoice_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("billing_invoices.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    invoice: Mapped[BillingInvoice] = relationship(BillingInvoice, back_populates="items")


class BillingPayment(BaseModel, TenantMixin):
    __tablename__ = "billing_payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("billing_invoices.id", ondelete="RESTRICT"), nullable=False)
    provider_reference: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    payment_method: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="EUR", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending, completed, failed, refunded
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_billing_payments_status", "status"),
    )


class BillingPaymentMethod(BaseModel, TenantMixin):
    __tablename__ = "billing_payment_methods"

    provider_key: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    card_brand: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    card_last4: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# ==============================================================================
# MODULES, USAGE, OUTBOX AND IDEMPOTENCY
# ==============================================================================

class AvailableModule(BaseModel):
    __tablename__ = "available_modules"

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    minimum_core_version: Mapped[str] = mapped_column(String(50), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=True)
    is_core: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_paid_addon: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    routes_prefix: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class TenantModule(BaseModel, TenantMixin):
    __tablename__ = "tenant_modules"

    module_key: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "module_key", name="uq_tenant_modules_tenant_module"),
    )


class UsageCounter(BaseModel, TenantMixin):
    __tablename__ = "usage_counters"

    metric_key: Mapped[str] = mapped_column(String(100), nullable=False)
    current_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "metric_key", "period_start", "period_end", name="uq_usage_counters_tenant_metric_period"),
        Index("ix_usage_counters_tenant_id_metric", "tenant_id", "metric_key"),
    )


class UsageEvent(BaseModel, TenantMixin):
    __tablename__ = "usage_events"

    metric_key: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        Index("ix_usage_events_tenant_metric_created", "tenant_id", "metric_key", "created_at"),
    )


class OutboxEvent(BaseModel):
    __tablename__ = "outbox_events"

    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    event_key: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending, processing, processed, failed, cancelled
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    __table_args__ = (
        Index("ix_outbox_events_status_retry", "status", "next_retry_at"),
    )


class IdempotencyKey(BaseModel):
    __tablename__ = "idempotency_keys"

    scope: Mapped[str] = mapped_column(String(100), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_body: Mapped[Optional[str]] = mapped_column(String(10000), nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="processing", nullable=False)  # processing, completed, failed, expired
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("scope", "key", name="uq_idempotency_keys_scope_key"),
    )


class TenantApiKey(BaseModel, TenantMixin):
    __tablename__ = "tenant_api_keys"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    scopes: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active, suspended, expired, revoked
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("tenant_users.id", ondelete="SET NULL"), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("tenant_users.id", ondelete="SET NULL"), nullable=True)

    tenant: Mapped[Tenant] = relationship(Tenant, back_populates="api_keys")
    logs: Mapped[List["TenantApiKeyLog"]] = relationship("TenantApiKeyLog", back_populates="api_key", cascade="all, delete-orphan")


class TenantApiKeyLog(BaseModel):
    __tablename__ = "tenant_api_key_logs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    api_key_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenant_api_keys.id", ondelete="CASCADE"), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    api_key: Mapped[TenantApiKey] = relationship(TenantApiKey, back_populates="logs")

    __table_args__ = (
        Index("ix_tenant_api_key_logs_tenant_created", "tenant_id", "created_at"),
    )


class WebhookSubscription(BaseModel, TenantMixin):
    __tablename__ = "webhook_subscriptions"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    events: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    encrypted_secret: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active, inactive
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("tenant_users.id", ondelete="SET NULL"), nullable=True)
    disabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped[Tenant] = relationship(Tenant, back_populates="webhook_subscriptions")
    deliveries: Mapped[List["WebhookDelivery"]] = relationship("WebhookDelivery", back_populates="webhook_subscription", cascade="all, delete-orphan")


class WebhookDelivery(BaseModel, TenantMixin):
    __tablename__ = "webhook_deliveries"

    webhook_subscription_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # pending, processing, delivered, failed
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    webhook_subscription: Mapped[WebhookSubscription] = relationship(WebhookSubscription, back_populates="deliveries")


# Automatic Cache Invalidation event listeners
from sqlalchemy import event

def db_invalidate_tenant_modules_cache(mapper, connection, target):
    try:
        from dymo_saas_core.core.cache_helpers import invalidate_tenant_modules_cache
        if hasattr(target, "tenant_id") and target.tenant_id:
            invalidate_tenant_modules_cache(target.tenant_id)
    except Exception:
        pass

def db_invalidate_tenant_cache(mapper, connection, target):
    try:
        from dymo_saas_core.core.cache_helpers import invalidate_tenant_cache
        invalidate_tenant_cache(target.id, target.slug)
    except Exception:
        pass

event.listen(TenantModule, "after_insert", db_invalidate_tenant_modules_cache)
event.listen(TenantModule, "after_update", db_invalidate_tenant_modules_cache)
event.listen(TenantModule, "after_delete", db_invalidate_tenant_modules_cache)

event.listen(Subscription, "after_insert", db_invalidate_tenant_modules_cache)
event.listen(Subscription, "after_update", db_invalidate_tenant_modules_cache)
event.listen(Subscription, "after_delete", db_invalidate_tenant_modules_cache)

event.listen(Tenant, "after_insert", db_invalidate_tenant_cache)
event.listen(Tenant, "after_update", db_invalidate_tenant_cache)
event.listen(Tenant, "after_delete", db_invalidate_tenant_cache)

