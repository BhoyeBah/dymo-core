import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.platform_context import require_platform_admin
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.core.exceptions import AppException
from dymo_saas_core.models.models import Plan, PlanPrice, PlanLimit, PlanFeature, PlanModule
from dymo_saas_core.platform.schemas import PlanCreateRequest

router = APIRouter(tags=["Platform Plans"])

@router.get("")
def list_plans(db: Session = Depends(get_db), admin = Depends(require_platform_admin)):
    plans = db.query(Plan).order_by(Plan.display_order.asc()).all()
    return success_response([
        {
            "id": str(p.id),
            "name": p.name,
            "slug": p.slug,
            "description": p.description,
            "status": p.status,
            "trial_enabled": p.trial_enabled,
            "trial_days": p.trial_days,
            "display_order": p.display_order
        }
        for p in plans
    ])

@router.post("")
def create_plan(body: PlanCreateRequest, db: Session = Depends(get_db), admin = Depends(require_platform_admin)):
    # Check if slug exists
    if db.query(Plan).filter(Plan.slug == body.slug).first():
        raise AppException("Plan slug already exists", "PLAN_SLUG_EXISTS", 409)
        
    plan = Plan(
        name=body.name,
        slug=body.slug,
        description=body.description,
        status="active",
        trial_enabled=body.trial_enabled,
        trial_days=body.trial_days,
        display_order=body.display_order
    )
    db.add(plan)
    db.flush()
    
    # Add Prices
    for p in body.prices:
        price = PlanPrice(
            plan_id=plan.id,
            billing_cycle=p.billing_cycle,
            currency=p.currency,
            amount=p.amount,
            setup_fee=p.setup_fee,
            is_active=True
        )
        db.add(price)
        
    # Add Limits
    for l in body.limits:
        limit = PlanLimit(
            plan_id=plan.id,
            metric_key=l.metric_key,
            limit_value=l.limit_value,
            period=l.period,
            overage_allowed=l.overage_allowed,
            overage_unit_price=l.overage_unit_price
        )
        db.add(limit)
        
    # Add Features
    for f in body.features:
        feature = PlanFeature(
            plan_id=plan.id,
            feature_key=f.feature_key,
            name=f.name,
            description=f.description
        )
        db.add(feature)
        
    # Add Modules
    for m in body.modules:
        pm = PlanModule(
            plan_id=plan.id,
            module_key=m
        )
        db.add(pm)
        
    db.commit()
    
    return success_response({
        "id": str(plan.id),
        "name": plan.name,
        "slug": plan.slug
    }, message="Subscription plan created successfully")
