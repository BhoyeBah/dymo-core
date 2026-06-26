from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Request, Header
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.security import (
    verify_password, create_access_token, create_refresh_token, hash_token, decode_token, coerce_uuid
)
from dymo_saas_core.core.exceptions import UnauthorizedException, ForbiddenException, NotFoundException, TenantSuspendedException
from dymo_saas_core.core.tenant_context import require_tenant_user
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.models.models import Tenant, TenantUser, TenantRefreshToken, TenantAuditLog
from dymo_saas_core.tenant_app.schemas import TenantLoginRequest

router = APIRouter(tags=["Tenant Auth"])

@router.post("/login")
def login(
    request: Request,
    body: TenantLoginRequest,
    db: Session = Depends(get_db),
    x_tenant_slug: str = Header(None, alias="X-Tenant-Slug"),
    x_tenant_id: str = Header(None, alias="X-Tenant-ID")
):
    tenant = None
    if x_tenant_id:
        tenant = db.query(Tenant).filter(Tenant.id == coerce_uuid(x_tenant_id)).first()
    elif x_tenant_slug:
        tenant = db.query(Tenant).filter(Tenant.slug == x_tenant_slug).first()
        
    if not tenant:
        raise NotFoundException("Tenant context required or invalid tenant identifier", "TENANT_CONTEXT_REQUIRED")
        
    if tenant.status == "suspended":
        raise TenantSuspendedException()
    if tenant.status not in ["active", "trial"]:
        raise ForbiddenException(f"Tenant account is inactive ({tenant.status})", "TENANT_INACTIVE")
        
    user = db.query(TenantUser).filter(
        TenantUser.tenant_id == tenant.id,
        TenantUser.email == body.email
    ).first()
    
    if not user or not verify_password(body.password, user.password_hash):
        raise UnauthorizedException("Invalid email or password", "INVALID_CREDENTIALS")
        
    if user.status != "active":
        raise ForbiddenException(f"User account status is {user.status}", "USER_INACTIVE")
        
    payload = {
        "user_id": str(user.id),
        "tenant_id": str(tenant.id),
        "user_type": "tenant_user"
    }
    access = create_access_token(payload)
    refresh = create_refresh_token(payload)
    
    db.query(TenantRefreshToken).filter(
        TenantRefreshToken.user_id == user.id,
        TenantRefreshToken.is_revoked == False
    ).update({"is_revoked": True})
    
    token_record = TenantRefreshToken(
        tenant_id=tenant.id,
        user_id=user.id,
        token_hash=hash_token(refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        is_revoked=False
    )
    db.add(token_record)
    
    audit_log = TenantAuditLog(
        tenant_id=tenant.id,
        user_id=user.id,
        action="tenant.login",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        payload={"email": body.email}
    )
    db.add(audit_log)
    db.commit()
    
    return success_response({
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "tenant_id": str(tenant.id),
        "tenant_slug": tenant.slug
    })

@router.post("/refresh")
def refresh_token(request: Request, refresh_token: str, db: Session = Depends(get_db)):
    payload = decode_token(refresh_token)
    
    if payload.get("type") != "refresh" or payload.get("user_type") != "tenant_user":
        raise UnauthorizedException("Invalid refresh token", "INVALID_TOKEN")
        
    user_id = coerce_uuid(payload.get("user_id"))
    tenant_id = coerce_uuid(payload.get("tenant_id"))
    refresh_hash = hash_token(refresh_token)
    
    token_record = db.query(TenantRefreshToken).filter(
        TenantRefreshToken.token_hash == refresh_hash,
        TenantRefreshToken.user_id == user_id,
        TenantRefreshToken.tenant_id == tenant_id,
        TenantRefreshToken.is_revoked == False
    ).first()
    
    if not token_record or token_record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise UnauthorizedException("Refresh token is expired or revoked", "TOKEN_EXPIRED")
        
    user = db.query(TenantUser).filter(
        TenantUser.id == user_id,
        TenantUser.tenant_id == tenant_id
    ).first()
    
    if not user or user.status != "active":
        raise UnauthorizedException("User account is inactive", "USER_INACTIVE")
        
    token_record.is_revoked = True
    
    new_payload = {
        "user_id": str(user.id),
        "tenant_id": str(tenant_id),
        "user_type": "tenant_user"
    }
    new_access = create_access_token(new_payload)
    new_refresh = create_refresh_token(new_payload)
    
    new_token_record = TenantRefreshToken(
        tenant_id=tenant_id,
        user_id=user.id,
        token_hash=hash_token(new_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        is_revoked=False
    )
    db.add(new_token_record)
    db.commit()
    
    return success_response({
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer"
    })

@router.get("/me")
def me(user = Depends(require_tenant_user)):
    return success_response({
        "id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "status": user.status
    })

@router.post("/logout")
def logout(refresh_token: str, db: Session = Depends(get_db), user = Depends(require_tenant_user)):
    refresh_hash = hash_token(refresh_token)
    db.query(TenantRefreshToken).filter(
        TenantRefreshToken.token_hash == refresh_hash,
        TenantRefreshToken.user_id == user.id,
        TenantRefreshToken.tenant_id == user.tenant_id
    ).update({"is_revoked": True})
    db.commit()
    return success_response(message="Logged out successfully")
