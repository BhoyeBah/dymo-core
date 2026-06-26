import secrets
import hashlib
import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.core.exceptions import NotFoundException, AppException
from dymo_saas_core.core.permissions import require_permission
from dymo_saas_core.models.models import TenantApiKey, TenantApiKeyLog
from dymo_saas_core.core.utils import write_audit_log
from dymo_saas_core.tenant_app.schemas import (
    ApiKeyCreateRequest, ApiKeyUpdateRequest, ApiKeyResponse,
    ApiKeyCreateResponse, ApiKeyLogResponse
)

router = APIRouter(tags=["Tenant API Keys"])

def generate_api_key():
    prefix = secrets.token_hex(8)  # 16 hex chars
    secret = secrets.token_urlsafe(32)
    raw_key = f"dymo_sk_{prefix}_{secret}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, prefix, key_hash

@router.post("/api-keys", response_model=dict, status_code=201)
def create_api_key(
    payload: ApiKeyCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("tenant.api_keys.create"))
):
    raw_key, prefix, key_hash = generate_api_key()
    
    api_key = TenantApiKey(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=payload.scopes,
        status="active",
        expires_at=payload.expires_at,
        created_by_user_id=current_user.id
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    write_audit_log(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="api_key.create",
        payload={"api_key_id": str(api_key.id), "name": api_key.name}
    )
    
    return success_response({
        "id": str(api_key.id),
        "name": api_key.name,
        "key_prefix": api_key.key_prefix,
        "scopes": api_key.scopes,
        "status": api_key.status,
        "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
        "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
        "created_at": api_key.created_at.isoformat(),
        "updated_at": api_key.updated_at.isoformat(),
        "raw_key": raw_key
    })

@router.get("/api-keys", response_model=dict)
def list_api_keys(
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("tenant.api_keys.view"))
):
    keys = db.query(TenantApiKey).filter(
        TenantApiKey.tenant_id == current_user.tenant_id
    ).order_by(TenantApiKey.created_at.desc()).all()
    
    return success_response([
        {
            "id": str(k.id),
            "name": k.name,
            "key_prefix": k.key_prefix,
            "scopes": k.scopes,
            "status": k.status,
            "expires_at": k.expires_at.isoformat() if k.expires_at else None,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "created_at": k.created_at.isoformat(),
            "updated_at": k.updated_at.isoformat()
        }
        for k in keys
    ])

@router.get("/api-keys/{key_id}", response_model=dict)
def get_api_key(
    key_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("tenant.api_keys.view"))
):
    key = db.query(TenantApiKey).filter(
        TenantApiKey.tenant_id == current_user.tenant_id,
        TenantApiKey.id == key_id
    ).first()
    if not key:
        raise NotFoundException("API key not found")
        
    return success_response({
        "id": str(key.id),
        "name": key.name,
        "key_prefix": key.key_prefix,
        "scopes": key.scopes,
        "status": key.status,
        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
        "created_at": key.created_at.isoformat(),
        "updated_at": key.updated_at.isoformat()
    })

@router.post("/api-keys/{key_id}/revoke", response_model=dict)
def revoke_api_key(
    key_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("tenant.api_keys.revoke"))
):
    key = db.query(TenantApiKey).filter(
        TenantApiKey.tenant_id == current_user.tenant_id,
        TenantApiKey.id == key_id
    ).first()
    if not key:
        raise NotFoundException("API key not found")
        
    key.status = "revoked"
    key.revoked_at = datetime.now(timezone.utc)
    key.revoked_by_user_id = current_user.id
    db.commit()
    
    write_audit_log(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="api_key.revoke",
        payload={"api_key_id": str(key.id)}
    )
    
    return success_response(message="API key revoked successfully")

@router.delete("/api-keys/{key_id}", response_model=dict)
def delete_api_key(
    key_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("tenant.api_keys.revoke"))
):
    key = db.query(TenantApiKey).filter(
        TenantApiKey.tenant_id == current_user.tenant_id,
        TenantApiKey.id == key_id
    ).first()
    if not key:
        raise NotFoundException("API key not found")
        
    db.delete(key)
    db.commit()
    
    write_audit_log(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        action="api_key.delete",
        payload={"api_key_id": str(key_id)}
    )
    
    return success_response(message="API key deleted successfully")

@router.get("/api-keys/{key_id}/logs", response_model=dict)
def get_api_key_logs(
    key_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("tenant.api_keys.logs.view"))
):
    key = db.query(TenantApiKey).filter(
        TenantApiKey.tenant_id == current_user.tenant_id,
        TenantApiKey.id == key_id
    ).first()
    if not key:
        raise NotFoundException("API key not found")
        
    logs = db.query(TenantApiKeyLog).filter(
        TenantApiKeyLog.tenant_id == current_user.tenant_id,
        TenantApiKeyLog.api_key_id == key_id
    ).order_by(TenantApiKeyLog.created_at.desc()).all()
    
    return success_response([
        {
            "id": str(l.id),
            "method": l.method,
            "path": l.path,
            "status_code": l.status_code,
            "ip_address": l.ip_address,
            "user_agent": l.user_agent,
            "created_at": l.created_at.isoformat()
        }
        for l in logs
    ])
