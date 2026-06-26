from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from dymo_saas_core.core.database import get_db
from dymo_saas_core.core.pagination import paginate_query
from dymo_saas_core.core.platform_context import require_platform_admin
from dymo_saas_core.core.responses import success_response
from dymo_saas_core.models.models import (
    BillingInvoice,
    BillingPayment,
    Plan,
    PlanPrice,
    Subscription,
    Tenant,
    UsageCounter,
    PlatformProviderConfig,
    PlatformProviderLog,
)

router = APIRouter(tags=["Platform Analytics"])


def _monthly_amount_for_subscription(db: Session, subscription: Subscription) -> float:
    monthly_price = (
        db.query(PlanPrice)
        .filter(PlanPrice.plan_id == subscription.plan_id, PlanPrice.billing_cycle == subscription.billing_cycle)
        .first()
    )
    if monthly_price:
        return float(monthly_price.amount) if subscription.billing_cycle == "monthly" else float(monthly_price.amount) / 12.0

    active_price = db.query(PlanPrice).filter(PlanPrice.plan_id == subscription.plan_id, PlanPrice.is_active == True).first()
    if not active_price:
        return 0.0
    if active_price.billing_cycle == "yearly":
        return float(active_price.amount) / 12.0
    return float(active_price.amount)


def _compute_overview(db: Session) -> dict[str, Any]:
    tenants = db.query(Tenant).all()
    subscriptions = db.query(Subscription).all()
    plans = {str(plan.id): plan for plan in db.query(Plan).all()}
    invoices = {str(invoice.id): invoice for invoice in db.query(BillingInvoice).all()}
    payments = db.query(BillingPayment).all()
    usage_counters = db.query(UsageCounter).all()

    active_subscriptions = [sub for sub in subscriptions if sub.status == "active"]
    trial_subscriptions = [sub for sub in subscriptions if sub.status == "trialing"]
    cancelled_subscriptions = [sub for sub in subscriptions if sub.status in {"cancelled", "expired", "unpaid", "suspended"}]

    mrr = sum(_monthly_amount_for_subscription(db, sub) for sub in active_subscriptions)
    arr = mrr * 12
    active_tenants = [tenant for tenant in tenants if tenant.status == "active"]
    trial_tenants = [tenant for tenant in tenants if tenant.status == "trial"]
    paying_tenants = {str(sub.tenant_id) for sub in active_subscriptions}

    successful_payments = [payment for payment in payments if payment.status in {"completed", "successful"}]
    failed_payments = [payment for payment in payments if payment.status == "failed"]
    refunded_payments = [payment for payment in payments if payment.status == "refunded"]

    revenue = sum(float(payment.amount) for payment in successful_payments)
    arpu = revenue / len(paying_tenants) if paying_tenants else 0.0
    churn_rate = (len(cancelled_subscriptions) / len(subscriptions)) if subscriptions else 0.0
    ltv = (arpu / churn_rate) if churn_rate > 0 else (arpu * 12 if arpu else 0.0)

    revenue_by_provider: dict[str, float] = defaultdict(float)
    revenue_by_country: dict[str, float] = defaultdict(float)
    revenue_by_plan: dict[str, float] = defaultdict(float)
    revenue_by_month: dict[str, float] = defaultdict(float)

    for payment in successful_payments:
        invoice = invoices.get(str(payment.invoice_id))
        if invoice:
            tenant = next((t for t in tenants if t.id == invoice.tenant_id), None)
            plan = plans.get(str(next((sub.plan_id for sub in subscriptions if sub.id == invoice.subscription_id), "")))
            country = tenant.country if tenant and tenant.country else "unknown"
            plan_slug = plan.slug if plan else "unknown"
            revenue_by_country[country] += float(payment.amount)
            revenue_by_plan[plan_slug] += float(payment.amount)

        provider_key = payment.payment_method or "unknown"
        revenue_by_provider[provider_key] += float(payment.amount)

        if payment.created_at:
            month_key = payment.created_at.strftime("%Y-%m")
            revenue_by_month[month_key] += float(payment.amount)

    usage_by_metric: dict[str, int] = defaultdict(int)
    for counter in usage_counters:
        usage_by_metric[counter.metric_key] += int(counter.current_value)

    subscription_breakdown = {
        "active": len(active_subscriptions),
        "trialing": len(trial_subscriptions),
        "cancelled": len(cancelled_subscriptions),
    }

    return {
        "mrr": round(mrr, 2),
        "arr": round(arr, 2),
        "arpu": round(arpu, 2),
        "churn_rate": round(churn_rate, 4),
        "estimated_ltv": round(ltv, 2),
        "tenants_active": len(active_tenants),
        "tenants_paying": len(paying_tenants),
        "tenants_trial": len(trial_tenants),
        "trial_to_paid_conversion_rate": round((len(active_subscriptions) / (len(active_subscriptions) + len(trial_subscriptions))) if (active_subscriptions or trial_subscriptions) else 0.0, 4),
        "payments_successful": len(successful_payments),
        "payments_failed": len(failed_payments),
        "payments_refunded": len(refunded_payments),
        "revenue_total": round(revenue, 2),
        "revenue_by_provider": dict(sorted(revenue_by_provider.items(), key=lambda item: item[0])),
        "revenue_by_country": dict(sorted(revenue_by_country.items(), key=lambda item: item[0])),
        "revenue_by_plan": dict(sorted(revenue_by_plan.items(), key=lambda item: item[0])),
        "revenue_by_month": dict(sorted(revenue_by_month.items(), key=lambda item: item[0])),
        "usage": dict(sorted(usage_by_metric.items(), key=lambda item: item[0])),
        "subscription_breakdown": subscription_breakdown,
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), admin = Depends(require_platform_admin)):
    overview = _compute_overview(db)
    return success_response(
        {
            "mrr": overview["mrr"],
            "arr": overview["arr"],
            "active_tenants": overview["tenants_active"],
            "paying_tenants": overview["tenants_paying"],
            "trial_tenants": overview["tenants_trial"],
            "successful_payments": overview["payments_successful"],
            "failed_payments": overview["payments_failed"],
            "churn_rate": overview["churn_rate"],
        }
    )


@router.get("/analytics/overview")
def analytics_overview(db: Session = Depends(get_db), admin = Depends(require_platform_admin)):
    return success_response(_compute_overview(db))


@router.get("/analytics/revenue")
def analytics_revenue(db: Session = Depends(get_db), admin = Depends(require_platform_admin)):
    overview = _compute_overview(db)
    return success_response(
        {
            "mrr": overview["mrr"],
            "arr": overview["arr"],
            "arpu": overview["arpu"],
            "revenue_total": overview["revenue_total"],
            "revenue_by_provider": overview["revenue_by_provider"],
            "revenue_by_country": overview["revenue_by_country"],
            "revenue_by_plan": overview["revenue_by_plan"],
            "revenue_by_month": overview["revenue_by_month"],
            "payments_successful": overview["payments_successful"],
            "payments_failed": overview["payments_failed"],
            "payments_refunded": overview["payments_refunded"],
        }
    )


@router.get("/analytics/tenants")
def analytics_tenants(db: Session = Depends(get_db), admin = Depends(require_platform_admin)):
    overview = _compute_overview(db)
    tenants = db.query(Tenant).all()
    status_breakdown: dict[str, int] = defaultdict(int)
    country_breakdown: dict[str, int] = defaultdict(int)
    for tenant in tenants:
        status_breakdown[tenant.status] += 1
        country_breakdown[tenant.country or "unknown"] += 1
    return success_response(
        {
            "active_tenants": overview["tenants_active"],
            "paying_tenants": overview["tenants_paying"],
            "trial_tenants": overview["tenants_trial"],
            "status_breakdown": dict(sorted(status_breakdown.items(), key=lambda item: item[0])),
            "country_breakdown": dict(sorted(country_breakdown.items(), key=lambda item: item[0])),
            "trial_to_paid_conversion_rate": overview["trial_to_paid_conversion_rate"],
        }
    )


@router.get("/analytics/providers")
def analytics_providers(db: Session = Depends(get_db), admin = Depends(require_platform_admin)):
    providers = db.query(PlatformProviderConfig).all()
    logs = db.query(PlatformProviderLog).all()
    logs_by_provider: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "failed": 0})
    for log in logs:
        key = f"{log.provider_type}:{log.provider_name}"
        logs_by_provider[key][log.status] = logs_by_provider[key].get(log.status, 0) + 1

    return success_response(
        [
            {
                "id": str(provider.id),
                "provider_type": provider.provider_type,
                "provider_name": provider.provider_name,
                "environment": provider.environment,
                "is_active": provider.is_active,
                "is_default": provider.is_default,
                "last_test_status": provider.last_test_status,
                "last_tested_at": provider.last_tested_at.isoformat() if provider.last_tested_at else None,
                "log_breakdown": logs_by_provider.get(f"{provider.provider_type}:{provider.provider_name}", {"success": 0, "failed": 0}),
            }
            for provider in providers
        ]
    )


@router.get("/analytics/usage")
def analytics_usage(db: Session = Depends(get_db), admin = Depends(require_platform_admin)):
    usage_counters = db.query(UsageCounter).all()
    usage: dict[str, int] = defaultdict(int)
    for counter in usage_counters:
        usage[counter.metric_key] += int(counter.current_value)
    return success_response(
        {
            "usage": dict(sorted(usage.items(), key=lambda item: item[0])),
            "total_usage_items": len(usage_counters),
        }
    )
