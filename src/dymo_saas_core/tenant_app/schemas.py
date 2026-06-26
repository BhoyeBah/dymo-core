from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
import uuid

# ==============================================================================
# AUTH SCHEMAS
# ==============================================================================

class TenantLoginRequest(BaseModel):
    email: EmailStr
    password: str

# ==============================================================================
# USER & ROLE SCHEMAS
# ==============================================================================

class TenantUserCreateRequest(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: str = Field(..., min_length=6)
    role_ids: List[uuid.UUID] = []

class TenantUserUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: Optional[str] = None  # active, inactive, suspended
    role_ids: Optional[List[uuid.UUID]] = None

# ==============================================================================
# INVITATION SCHEMAS
# ==============================================================================

class TenantInvitationCreateRequest(BaseModel):
    email: EmailStr
    role_id: uuid.UUID

# ==============================================================================
# BILLING & PLAN SCHEMAS
# ==============================================================================

class SubscriptionChangeRequest(BaseModel):
    plan_id: uuid.UUID
    billing_cycle: str  # monthly, yearly

class StripeCheckoutRequest(BaseModel):
    plan_id: uuid.UUID
    billing_cycle: str = "monthly"
    success_url: str
    cancel_url: str

class StripePortalRequest(BaseModel):
    return_url: str

# ==============================================================================
# ROLE & PERMISSION SCHEMAS
# ==============================================================================

class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)

class RoleUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)

class RolePermissionsAssignRequest(BaseModel):
    permission_ids: List[uuid.UUID]

# ==============================================================================
# API KEY SCHEMAS
# ==============================================================================

class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: List[str] = []
    expires_at: Optional[datetime] = None

class ApiKeyUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    scopes: Optional[List[str]] = None
    status: Optional[str] = None  # active, suspended, expired, revoked
    expires_at: Optional[datetime] = None

class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: List[str]
    status: str
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ApiKeyCreateResponse(ApiKeyResponse):
    raw_key: str

class ApiKeyLogResponse(BaseModel):
    id: uuid.UUID
    method: str
    path: str
    status_code: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# WEBHOOK SCHEMAS
# ==============================================================================

class WebhookSubscriptionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    target_url: str = Field(..., min_length=1, max_length=500)
    events: List[str] = Field(default_factory=list)

class WebhookSubscriptionUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    target_url: Optional[str] = Field(None, min_length=1, max_length=500)
    events: Optional[List[str]] = None
    status: Optional[str] = None  # active, inactive

class WebhookSubscriptionResponse(BaseModel):
    id: uuid.UUID
    name: str
    target_url: str
    events: List[str]
    status: str
    disabled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class WebhookSubscriptionCreateResponse(WebhookSubscriptionResponse):
    secret: str

class WebhookDeliveryResponse(BaseModel):
    id: uuid.UUID
    webhook_subscription_id: uuid.UUID
    event_type: str
    payload: dict
    status: str
    attempt_count: int
    last_status_code: Optional[int] = None
    last_error: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

