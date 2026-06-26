import logging
import sys
import structlog

def setup_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

def setup_sentry() -> None:
    from dymo_saas_core.core.config import settings
    if settings.SENTRY_DSN:
        try:
            import sentry_sdk
            
            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                environment=settings.ENVIRONMENT,
                traces_sample_rate=1.0,
                profiles_sample_rate=1.0
            )
            print(f"Sentry initialized successfully for environment: {settings.ENVIRONMENT}")
        except Exception as e:
            print(f"Failed to initialize Sentry: {e}")

logger = structlog.get_logger()
setup_logging()
setup_sentry()
