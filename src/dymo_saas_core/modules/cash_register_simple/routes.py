from datetime import date
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.core.tenant_context import require_tenant_user, require_active_tenant
from dymo_saas_core.core.module_registry import require_module
from dymo_saas_core.core.permissions import require_permission
from dymo_saas_core.modules.cash_register_simple.schemas import (
    SaleCreate, SaleResponse, SaleCancelRequest,
    DayClosureCreate, DayClosureResponse, DailyReportResponse
)
from dymo_saas_core.modules.cash_register_simple import services

router = APIRouter()

@router.get(
    "/sales",
    response_model=List[SaleResponse],
    dependencies=[
        Depends(require_tenant_user),
        Depends(require_active_tenant),
        Depends(require_module("cash_register_simple")),
        Depends(require_permission("cash_register_simple.sales.view"))
    ]
)
def list_sales(
    start_date: Optional[date] = Query(None, description="Filter sales from start date"),
    end_date: Optional[date] = Query(None, description="Filter sales until end date"),
    db: Session = Depends(get_db),
    tenant_user = Depends(require_tenant_user)
):
    sales = services.get_sales(db, tenant_user.tenant_id, start_date, end_date)
    return sales


@router.post(
    "/sales",
    response_model=SaleResponse,
    dependencies=[
        Depends(require_tenant_user),
        Depends(require_active_tenant),
        Depends(require_module("cash_register_simple")),
        Depends(require_permission("cash_register_simple.sales.create"))
    ]
)
def create_sale(
    body: SaleCreate,
    db: Session = Depends(get_db),
    tenant_user = Depends(require_tenant_user)
):
    sale = services.create_sale(db, tenant_user.tenant_id, tenant_user.id, body)
    return sale


@router.get(
    "/sales/{id}",
    response_model=SaleResponse,
    dependencies=[
        Depends(require_tenant_user),
        Depends(require_active_tenant),
        Depends(require_module("cash_register_simple")),
        Depends(require_permission("cash_register_simple.sales.view"))
    ]
)
def get_sale(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_user = Depends(require_tenant_user)
):
    sale = services.get_sale_by_id(db, tenant_user.tenant_id, id)
    return sale


@router.post(
    "/sales/{id}/cancel",
    response_model=SaleResponse,
    dependencies=[
        Depends(require_tenant_user),
        Depends(require_active_tenant),
        Depends(require_module("cash_register_simple")),
        Depends(require_permission("cash_register_simple.sales.cancel"))
    ]
)
def cancel_sale(
    id: uuid.UUID,
    body: SaleCancelRequest,
    db: Session = Depends(get_db),
    tenant_user = Depends(require_tenant_user)
):
    sale = services.cancel_sale(db, tenant_user.tenant_id, tenant_user.id, id, body.cancellation_reason)
    return sale


@router.post(
    "/closures",
    response_model=DayClosureResponse,
    dependencies=[
        Depends(require_tenant_user),
        Depends(require_active_tenant),
        Depends(require_module("cash_register_simple")),
        Depends(require_permission("cash_register_simple.closures.create"))
    ]
)
def create_day_closure(
    body: DayClosureCreate,
    db: Session = Depends(get_db),
    tenant_user = Depends(require_tenant_user)
):
    closure = services.create_day_closure(db, tenant_user.tenant_id, tenant_user.id, body)
    return closure


@router.get(
    "/closures",
    response_model=List[DayClosureResponse],
    dependencies=[
        Depends(require_tenant_user),
        Depends(require_active_tenant),
        Depends(require_module("cash_register_simple")),
        Depends(require_permission("cash_register_simple.closures.view"))
    ]
)
def list_closures(
    db: Session = Depends(get_db),
    tenant_user = Depends(require_tenant_user)
):
    closures = services.get_closures(db, tenant_user.tenant_id)
    return closures


@router.get(
    "/reports/daily",
    response_model=DailyReportResponse,
    dependencies=[
        Depends(require_tenant_user),
        Depends(require_active_tenant),
        Depends(require_module("cash_register_simple")),
        Depends(require_permission("cash_register_simple.reports.view"))
    ]
)
def get_daily_report(
    report_date: Optional[date] = Query(None, alias="date", description="Report date"),
    db: Session = Depends(get_db),
    tenant_user = Depends(require_tenant_user)
):
    if not report_date:
        report_date = date.today()
    report = services.get_daily_report(db, tenant_user.tenant_id, report_date)
    return report
