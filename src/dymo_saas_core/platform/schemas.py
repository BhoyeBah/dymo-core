from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
import uuid

# ==============================================================================
# AUTH SCHEMAS
# ==============================================================================

class PlatformLoginRequest(BaseModel):
    email: EmailStr
    password: str

class PlatformTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class PlatformAdminResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

# ==============================================================================
# TENANT SCHEMAS
# ==============================================================================

class TenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100)
    owner_email: EmailStr
    owner_phone: Optional[str] = None
    country: Optional[str] = None
    currency: str = "EUR"
    timezone: str = "UTC"
    language: str = "fr"

class TenantUpdateRequest(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None  # pending, trial, active, past_due, suspended, cancelled, deleted
    owner_phone: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None

class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    owner_email: EmailStr
    owner_phone: Optional[str]
    country: Optional[str]
    currency: str
    timezone: str
    language: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ==============================================================================
# PLAN & BILLING SCHEMAS
# ==============================================================================

class PlanPriceCreate(BaseModel):
    billing_cycle: str  # monthly, yearly
    currency: str = "EUR"
    amount: float
    setup_fee: float = 0.0

class PlanLimitCreate(BaseModel):
    metric_key: str
    limit_value: int
    period: str = "monthly"
    overage_allowed: bool = False
    overage_unit_price: float = 0.0

class PlanFeatureCreate(BaseModel):
    feature_key: str
    name: str
    description: Optional[str] = None

class PlanCreateRequest(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    trial_enabled: bool = False
    trial_days: int = 0
    display_order: int = 0
    prices: List[PlanPriceCreate] = []
    limits: List[PlanLimitCreate] = []
    features: List[PlanFeatureCreate] = []
    modules: List[str] = []  # list of module keys

class PlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: Optional[str]
    status: str
    trial_enabled: bool
    trial_days: int
    display_order: int

    model_config = ConfigDict(from_attributes=True)

# ==============================================================================
# MODULE SCHEMAS
# ==============================================================================

class ModuleResponse(BaseModel):
    key: str
    name: str
    description: Optional[str]
    version: str
    minimum_core_version: str
    category: Optional[str]
    is_core: bool
    is_paid_addon: bool
    routes_prefix: Optional[str]

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# PLATFORM PROVIDERS / PAYMENTS / ANALYTICS / AUDIT
# ==============================================================================

class ProviderCredentialsRequest(BaseModel):
    model_config = ConfigDict(extra="allow")


class ProviderCreateRequest(BaseModel):
    provider_type: str = Field(..., min_length=2, max_length=50)
    provider_name: str = Field(..., min_length=2, max_length=100)
    environment: str = Field(default="production", max_length=50)
    credentials: dict
    is_active: bool = True
    is_default: bool = False
    supported_countries: List[str] = []
    supported_currencies: List[str] = []


class ProviderUpdateRequest(BaseModel):
    provider_type: Optional[str] = Field(default=None, min_length=2, max_length=50)
    provider_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    environment: Optional[str] = Field(default=None, max_length=50)
    credentials: Optional[dict] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    supported_countries: Optional[List[str]] = None
    supported_currencies: Optional[List[str]] = None


class ProviderTestRequest(BaseModel):
    payload: dict = {}


class PaymentRetryRequest(BaseModel):
    reason: Optional[str] = None


class PaymentRefundRequest(BaseModel):
    amount: Optional[float] = None
    reason: Optional[str] = None


class PlatformAnalyticsQuery(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class AuditLogsQuery(BaseModel):
    tenant_id: Optional[uuid.UUID] = None
    action: Optional[str] = None
    page: int = 1
    per_page: int = 20
