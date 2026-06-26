from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.encryption import encrypt_secret, decrypt_secret
from dymo_saas_core.core.exceptions import AppException, NotFoundException
from dymo_saas_core.core.pagination import paginate_query
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.core.security import coerce_uuid
from dymo_saas_core.models.models import PlatformProviderConfig, PlatformProviderLog, PlatformAuditLog
from dymo_saas_core.platform.schemas import ProviderCreateRequest, ProviderUpdateRequest, ProviderTestRequest
from dymo_saas_core.core.platform_context import require_platform_admin

router = APIRouter(prefix="/providers", tags=["Platform Providers"])


def _mask_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _mask_value(sub_value) for key, sub_value in value.items()}
    if isinstance(value, list):
        return [_mask_value(item) for item in value]
    if isinstance(value, str):
        if len(value) <= 4:
            return "****"
        return f"****{value[-4:]}"
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return "****"


def _load_credentials(encrypted_credentials: str) -> dict:
    raw = decrypt_secret(encrypted_credentials)
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _serialize_provider(provider: PlatformProviderConfig) -> dict:
    return {
        "id": str(provider.id),
        "provider_type": provider.provider_type,
        "provider_name": provider.provider_name,
        "environment": provider.environment,
        "is_active": provider.is_active,
        "is_default": provider.is_default,
        "supported_countries": provider.supported_countries or [],
        "supported_currencies": provider.supported_currencies or [],
        "last_test_status": provider.last_test_status,
        "last_tested_at": provider.last_tested_at.isoformat() if provider.last_tested_at else None,
        "created_at": provider.created_at.isoformat(),
        "updated_at": provider.updated_at.isoformat(),
        "credentials_masked": _mask_value(_load_credentials(provider.encrypted_credentials)),
    }


def _log_provider_event(
    db: Session,
    provider: PlatformProviderConfig,
    operation: str,
    status: str,
    request_payload: dict,
    response_payload: dict,
    error_message: str | None = None,
    duration_ms: int | None = None,
) -> PlatformProviderLog:
    log = PlatformProviderLog(
        provider_config_id=provider.id,
        provider_type=provider.provider_type,
        provider_name=provider.provider_name,
        operation=operation,
        status=status,
        request_payload_masked=_mask_value(request_payload),
        response_payload_masked=_mask_value(response_payload),
        error_message=error_message,
        duration_ms=duration_ms,
    )
    db.add(log)
    return log


def _write_platform_audit_log(
    db: Session,
    admin_id: uuid.UUID | None,
    action: str,
    payload: dict,
) -> None:
    db.add(
        PlatformAuditLog(
            admin_id=admin_id,
            action=action,
            payload=payload,
        )
    )


@router.get("")
def list_providers(
    provider_type: str | None = None,
    environment: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin),
):
    query = db.query(PlatformProviderConfig).order_by(PlatformProviderConfig.created_at.desc())
    if provider_type:
        query = query.filter(PlatformProviderConfig.provider_type == provider_type)
    if environment:
        query = query.filter(PlatformProviderConfig.environment == environment)
    if is_active is not None:
        query = query.filter(PlatformProviderConfig.is_active == is_active)
    providers, meta = paginate_query(db, query, page, per_page)
    return success_response([_serialize_provider(provider) for provider in providers], meta=meta)


@router.post("", status_code=201)
def create_provider(
    body: ProviderCreateRequest,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin),
):
    encrypted_credentials = encrypt_secret(json.dumps(body.credentials, ensure_ascii=False))
    provider = PlatformProviderConfig(
        provider_type=body.provider_type,
        provider_name=body.provider_name,
        environment=body.environment,
        encrypted_credentials=encrypted_credentials,
        is_active=body.is_active,
        is_default=body.is_default,
        supported_countries=body.supported_countries,
        supported_currencies=body.supported_currencies,
        created_by_user_id=admin.id,
        updated_by_user_id=admin.id,
    )
    db.add(provider)
    db.flush()

    if provider.is_default:
        db.query(PlatformProviderConfig).filter(
            PlatformProviderConfig.id != provider.id,
            PlatformProviderConfig.provider_type == provider.provider_type,
            PlatformProviderConfig.environment == provider.environment,
        ).update({"is_default": False})

    db.refresh(provider)

    _write_platform_audit_log(db=db, admin_id=admin.id, action="provider_created", payload=_serialize_provider(provider))
    db.commit()
    return success_response(_serialize_provider(provider), message="Provider created successfully")


@router.get("/{provider_id}")
def get_provider(
    provider_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin),
):
    provider = db.query(PlatformProviderConfig).filter(PlatformProviderConfig.id == provider_id).first()
    if not provider:
        raise NotFoundException("Provider not found", "PROVIDER_NOT_FOUND")
    return success_response(_serialize_provider(provider))


@router.patch("/{provider_id}")
def update_provider(
    provider_id: uuid.UUID,
    body: ProviderUpdateRequest,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin),
):
    provider = db.query(PlatformProviderConfig).filter(PlatformProviderConfig.id == provider_id).first()
    if not provider:
        raise NotFoundException("Provider not found", "PROVIDER_NOT_FOUND")

    before = _serialize_provider(provider)
    if body.provider_type is not None:
        provider.provider_type = body.provider_type
    if body.provider_name is not None:
        provider.provider_name = body.provider_name
    if body.environment is not None:
        provider.environment = body.environment
    if body.credentials is not None:
        provider.encrypted_credentials = encrypt_secret(json.dumps(body.credentials, ensure_ascii=False))
    if body.is_active is not None:
        provider.is_active = body.is_active
    if body.is_default is not None:
        provider.is_default = body.is_default
    if body.supported_countries is not None:
        provider.supported_countries = body.supported_countries
    if body.supported_currencies is not None:
        provider.supported_currencies = body.supported_currencies
    provider.updated_by_user_id = admin.id

    if provider.is_default:
        db.query(PlatformProviderConfig).filter(
            PlatformProviderConfig.id != provider.id,
            PlatformProviderConfig.provider_type == provider.provider_type,
            PlatformProviderConfig.environment == provider.environment,
        ).update({"is_default": False})

    _write_platform_audit_log(
        db=db,
        admin_id=admin.id,
        action="provider_updated",
        payload={"before": before, "after": _serialize_provider(provider)},
    )
    db.commit()
    db.refresh(provider)
    return success_response(_serialize_provider(provider), message="Provider updated successfully")


@router.post("/{provider_id}/test")
def test_provider(
    provider_id: uuid.UUID,
    body: ProviderTestRequest,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin),
):
    provider = db.query(PlatformProviderConfig).filter(PlatformProviderConfig.id == provider_id).first()
    if not provider:
        raise NotFoundException("Provider not found", "PROVIDER_NOT_FOUND")

    start = time.perf_counter()
    credentials = _load_credentials(provider.encrypted_credentials)
    request_payload = {
        "provider_id": str(provider.id),
        "provider_type": provider.provider_type,
        "provider_name": provider.provider_name,
        "payload": body.payload,
    }

    if not provider.is_active:
        provider.last_test_status = "failed"
        provider.last_tested_at = datetime.now(timezone.utc)
        response_payload = {"status": "failed", "reason": "provider_inactive"}
        _log_provider_event(
            db=db,
            provider=provider,
            operation="test",
            status="failed",
            request_payload=request_payload,
            response_payload=response_payload,
            error_message="Provider is inactive",
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        _write_platform_audit_log(db=db, admin_id=admin.id, action="provider_tested", payload=response_payload)
        db.commit()
        raise AppException("Provider is inactive", "PROVIDER_INACTIVE", 409)

    if not credentials:
        provider.last_test_status = "failed"
        provider.last_tested_at = datetime.now(timezone.utc)
        response_payload = {"status": "failed", "reason": "missing_credentials"}
        _log_provider_event(
            db=db,
            provider=provider,
            operation="test",
            status="failed",
            request_payload=request_payload,
            response_payload=response_payload,
            error_message="Missing credentials",
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        _write_platform_audit_log(db=db, admin_id=admin.id, action="provider_tested", payload=response_payload)
        db.commit()
        raise AppException("Provider credentials are missing", "PROVIDER_CREDENTIALS_MISSING", 400)

    provider.last_test_status = "success"
    provider.last_tested_at = datetime.now(timezone.utc)
    response_payload = {
        "status": "success",
        "provider_id": str(provider.id),
        "provider_name": provider.provider_name,
    }
    _log_provider_event(
        db=db,
        provider=provider,
        operation="test",
        status="success",
        request_payload=request_payload,
        response_payload=response_payload,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )
    _write_platform_audit_log(db=db, admin_id=admin.id, action="provider_tested", payload=response_payload)
    db.commit()
    db.refresh(provider)
    return success_response(response_payload, message="Provider test successful")


@router.post("/{provider_id}/activate")
def activate_provider(
    provider_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin),
):
    provider = db.query(PlatformProviderConfig).filter(PlatformProviderConfig.id == provider_id).first()
    if not provider:
        raise NotFoundException("Provider not found", "PROVIDER_NOT_FOUND")
    provider.is_active = True
    provider.updated_by_user_id = admin.id
    _write_platform_audit_log(db=db, admin_id=admin.id, action="provider_activated", payload=_serialize_provider(provider))
    db.commit()
    db.refresh(provider)
    return success_response(_serialize_provider(provider), message="Provider activated successfully")


@router.post("/{provider_id}/deactivate")
def deactivate_provider(
    provider_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin),
):
    provider = db.query(PlatformProviderConfig).filter(PlatformProviderConfig.id == provider_id).first()
    if not provider:
        raise NotFoundException("Provider not found", "PROVIDER_NOT_FOUND")
    provider.is_active = False
    provider.updated_by_user_id = admin.id
    _write_platform_audit_log(db=db, admin_id=admin.id, action="provider_deactivated", payload=_serialize_provider(provider))
    db.commit()
    db.refresh(provider)
    return success_response(_serialize_provider(provider), message="Provider deactivated successfully")

