from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.pagination import paginate_query
from dymo_saas_core.core.platform_context import require_platform_admin
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.models.models import PlatformAuditLog, TenantAuditLog, Tenant

router = APIRouter(tags=["Platform Audit Logs"])


def _serialize_platform_log(log: PlatformAuditLog) -> dict:
    return {
        "id": str(log.id),
        "scope": "platform",
        "tenant_id": None,
        "actor_id": str(log.admin_id) if log.admin_id else None,
        "action": log.action,
        "ip_address": log.ip_address,
        "user_agent": log.user_agent,
        "payload": log.payload,
        "created_at": log.created_at.isoformat(),
    }


def _serialize_tenant_log(log: TenantAuditLog) -> dict:
    return {
        "id": str(log.id),
        "scope": "tenant",
        "tenant_id": str(log.tenant_id) if log.tenant_id else None,
        "actor_id": str(log.user_id) if log.user_id else None,
        "action": log.action,
        "ip_address": log.ip_address,
        "user_agent": log.user_agent,
        "payload": log.payload,
        "created_at": log.created_at.isoformat(),
    }


@router.get("/audit-logs")
def list_audit_logs(
    scope: str = "all",
    tenant_id: uuid.UUID | None = None,
    action: str | None = None,
    page: int = 1,
    per_page: int = 20,
    db: Session = Depends(get_db),
    admin = Depends(require_platform_admin),
):
    entries: list[dict] = []

    if scope in {"all", "platform"}:
        platform_query = db.query(PlatformAuditLog).order_by(PlatformAuditLog.created_at.desc())
        if action:
            platform_query = platform_query.filter(PlatformAuditLog.action == action)
        platform_logs = platform_query.all()
        entries.extend(_serialize_platform_log(log) for log in platform_logs)

    if scope in {"all", "tenant"}:
        tenant_query = db.query(TenantAuditLog).order_by(TenantAuditLog.created_at.desc())
        if tenant_id is not None:
            tenant_query = tenant_query.filter(TenantAuditLog.tenant_id == tenant_id)
        if action:
            tenant_query = tenant_query.filter(TenantAuditLog.action == action)
        tenant_logs = tenant_query.all()
        entries.extend(_serialize_tenant_log(log) for log in tenant_logs)

    entries.sort(key=lambda item: item["created_at"], reverse=True)
    total = len(entries)
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20
    elif per_page > 100:
        per_page = 100
    start = (page - 1) * per_page
    end = start + per_page
    items = entries[start:end]
    meta = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": (total + per_page - 1) // per_page if total > 0 else 0,
    }
    return success_response(items, meta=meta)
