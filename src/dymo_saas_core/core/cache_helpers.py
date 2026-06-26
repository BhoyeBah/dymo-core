import structlog
from dymo_saas_core.core.cache import cache_service

logger = structlog.get_logger(__name__)

def invalidate_tenant_cache(tenant_id: str, slug: str = None) -> None:
    """
    Invalidates cached tenant details by tenant ID and optionally by slug.
    """
    try:
        cache_service.delete(f"dymo:tenant:id:{tenant_id}")
        if slug:
            cache_service.delete(f"dymo:tenant:slug:{slug}")
        logger.info("Invalidated tenant cache", tenant_id=str(tenant_id), slug=slug)
    except Exception as e:
        logger.error("Failed to invalidate tenant cache", tenant_id=str(tenant_id), error=str(e))

def invalidate_user_permissions_cache(tenant_id: str, user_id: str) -> None:
    """
    Invalidates cached flat permission list for a specific tenant user.
    """
    try:
        cache_service.delete(f"dymo:tenant_user_permissions:{tenant_id}:{user_id}")
        logger.info("Invalidated user permissions cache", tenant_id=str(tenant_id), user_id=str(user_id))
    except Exception as e:
        logger.error("Failed to invalidate user permissions cache", tenant_id=str(tenant_id), user_id=str(user_id), error=str(e))

def invalidate_tenant_modules_cache(tenant_id: str) -> None:
    """
    Invalidates cached list of active modules for a tenant.
    """
    try:
        cache_service.delete(f"dymo:tenant_modules:{tenant_id}")
        logger.info("Invalidated tenant modules cache", tenant_id=str(tenant_id))
    except Exception as e:
        logger.error("Failed to invalidate tenant modules cache", tenant_id=str(tenant_id), error=str(e))
