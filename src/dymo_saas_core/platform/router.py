from fastapi import APIRouter

from dymo_saas_core.platform.auth import router as auth_router
from dymo_saas_core.platform.audit_logs import router as audit_logs_router
from dymo_saas_core.platform.analytics import router as analytics_router
from dymo_saas_core.platform.payments import router as payments_router
from dymo_saas_core.platform.provider_logs import router as provider_logs_router
from dymo_saas_core.platform.providers import router as providers_router
from dymo_saas_core.platform.tenants import router as tenants_router
from dymo_saas_core.platform.plans import router as plans_router
from dymo_saas_core.platform.modules import router as modules_router

platform_router = APIRouter()

platform_router.include_router(auth_router, prefix="/auth")
platform_router.include_router(tenants_router, prefix="/tenants")
platform_router.include_router(plans_router, prefix="/plans")
platform_router.include_router(modules_router, prefix="/modules")
platform_router.include_router(providers_router)
platform_router.include_router(provider_logs_router)
platform_router.include_router(analytics_router)
platform_router.include_router(payments_router)
platform_router.include_router(audit_logs_router)
