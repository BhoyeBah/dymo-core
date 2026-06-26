from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.pagination import paginate_query
from dymo_saas_core.core.platform_context import require_platform_admin
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.models.models import PlatformProviderLog

router = APIRouter(tags=["Platform Provider Logs"])


@router.get("/provider-logs")
def list_provider_logs(
    provider_id: uuid.UUID | None = None,
    provider_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin),
):
    query = db.query(PlatformProviderLog).order_by(PlatformProviderLog.created_at.desc())
    if provider_id is not None:
        query = query.filter(PlatformProviderLog.provider_config_id == provider_id)
    if provider_type:
        query = query.filter(PlatformProviderLog.provider_type == provider_type)
    if status:
        query = query.filter(PlatformProviderLog.status == status)
    logs, meta = paginate_query(db, query, page, per_page)
    return success_response(
        [
            {
                "id": str(log.id),
                "provider_config_id": str(log.provider_config_id),
                "provider_type": log.provider_type,
                "provider_name": log.provider_name,
                "operation": log.operation,
                "status": log.status,
                "request_payload_masked": log.request_payload_masked,
                "response_payload_masked": log.response_payload_masked,
                "error_message": log.error_message,
                "duration_ms": log.duration_ms,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        meta=meta,
    )
