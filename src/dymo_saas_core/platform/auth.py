from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.security import (
    verify_password, create_access_token, create_refresh_token, hash_token, decode_token, coerce_uuid
)
from dymo_saas_core.core.exceptions import UnauthorizedException
from dymo_saas_core.core.platform_context import require_platform_admin
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.models.models import PlatformAdmin, PlatformRefreshToken, PlatformAuditLog
from dymo_saas_core.platform.schemas import PlatformLoginRequest

router = APIRouter(tags=["Platform Auth"])

@router.post("/login")
def login(request: Request, body: PlatformLoginRequest, db: Session = Depends(get_db)):
    admin = db.query(PlatformAdmin).filter(PlatformAdmin.email == body.email).first()
    if not admin or not verify_password(body.password, admin.password_hash):
        raise UnauthorizedException("Invalid email or password", "INVALID_CREDENTIALS")
        
    if not admin.is_active:
        raise UnauthorizedException("Admin account is suspended", "ADMIN_SUSPENDED")
        
    payload = {"admin_id": str(admin.id), "user_type": "platform_admin"}
    access = create_access_token(payload)
    refresh = create_refresh_token(payload)
    
    # Store refresh token
    refresh_hash = hash_token(refresh)
    
    # Revoke previous active tokens to enforce single session or clean up
    db.query(PlatformRefreshToken).filter(
        PlatformRefreshToken.admin_id == admin.id,
        PlatformRefreshToken.is_revoked == False
    ).update({"is_revoked": True})
    
    token_record = PlatformRefreshToken(
        admin_id=admin.id,
        token_hash=refresh_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        is_revoked=False
    )
    db.add(token_record)
    
    # Create audit log
    audit_log = PlatformAuditLog(
        admin_id=admin.id,
        action="platform.login",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        payload={"email": body.email}
    )
    db.add(audit_log)
    db.commit()
    
    return success_response({
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer"
    })

@router.post("/refresh")
def refresh_token(request: Request, refresh_token: str, db: Session = Depends(get_db)):
    payload = decode_token(refresh_token)
    
    if payload.get("type") != "refresh" or payload.get("user_type") != "platform_admin":
        raise UnauthorizedException("Invalid refresh token", "INVALID_TOKEN")
        
    admin_id = coerce_uuid(payload.get("admin_id"))
    refresh_hash = hash_token(refresh_token)
    
    token_record = db.query(PlatformRefreshToken).filter(
        PlatformRefreshToken.token_hash == refresh_hash,
        PlatformRefreshToken.admin_id == admin_id,
        PlatformRefreshToken.is_revoked == False
    ).first()
    
    if not token_record or token_record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise UnauthorizedException("Refresh token is expired or revoked", "TOKEN_EXPIRED")
        
    admin = db.query(PlatformAdmin).filter(PlatformAdmin.id == admin_id).first()
    if not admin or not admin.is_active:
        raise UnauthorizedException("Admin account is inactive", "ADMIN_INACTIVE")
        
    # Rotate refresh token (revoke old, generate new)
    token_record.is_revoked = True
    
    new_payload = {"admin_id": str(admin.id), "user_type": "platform_admin"}
    new_access = create_access_token(new_payload)
    new_refresh = create_refresh_token(new_payload)
    
    new_token_record = PlatformRefreshToken(
        admin_id=admin.id,
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
def me(admin = Depends(require_platform_admin)):
    return success_response({
        "id": str(admin.id),
        "email": admin.email,
        "first_name": admin.first_name,
        "last_name": admin.last_name,
        "is_active": admin.is_active
    })

@router.post("/logout")
def logout(refresh_token: str, db: Session = Depends(get_db), admin = Depends(require_platform_admin)):
    refresh_hash = hash_token(refresh_token)
    db.query(PlatformRefreshToken).filter(
        PlatformRefreshToken.token_hash == refresh_hash,
        PlatformRefreshToken.admin_id == admin.id
    ).update({"is_revoked": True})
    db.commit()
    return success_response(message="Logged out successfully")
