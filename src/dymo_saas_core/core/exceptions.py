from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from dymo_saas_core.core.responses import error_response

class AppException(Exception):
    def __init__(self, message: str, error_code: str, status_code: int = 400, details: dict = None):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized", error_code: str = "UNAUTHORIZED", details: dict = None):
        super().__init__(message, error_code, 401, details)

class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden", error_code: str = "FORBIDDEN", details: dict = None):
        super().__init__(message, error_code, 403, details)

class NotFoundException(AppException):
    def __init__(self, message: str = "Not Found", error_code: str = "NOT_FOUND", details: dict = None):
        super().__init__(message, error_code, 404, details)

class ValidationException(AppException):
    def __init__(self, message: str = "Validation Error", error_code: str = "VALIDATION_ERROR", details: dict = None):
        super().__init__(message, error_code, 422, details)

class TenantSuspendedException(AppException):
    def __init__(self, message: str = "Tenant is suspended", error_code: str = "TENANT_SUSPENDED", details: dict = None):
        super().__init__(message, error_code, 403, details)

class QuotaExceededException(AppException):
    def __init__(self, message: str = "Quota exceeded", error_code: str = "QUOTA_EXCEEDED", details: dict = None):
        super().__init__(message, error_code, 402, details)

class ModuleNotEnabledException(AppException):
    def __init__(self, message: str = "Module not enabled for this tenant", error_code: str = "MODULE_NOT_ENABLED", details: dict = None):
        super().__init__(message, error_code, 403, details)

class IdempotencyException(AppException):
    def __init__(self, message: str = "Idempotency conflict", error_code: str = "IDEMPOTENCY_CONFLICT", details: dict = None):
        super().__init__(message, error_code, 409, details)

class IdempotencyReturnResponseException(Exception):
    def __init__(self, status_code: int, response_body: str):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"Cached response: {status_code}")



def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(exc.message, exc.error_code, exc.details)
        )

    @app.exception_handler(IdempotencyReturnResponseException)
    async def idempotency_return_response_handler(request: Request, exc: IdempotencyReturnResponseException):
        from fastapi.responses import Response
        return Response(
            content=exc.response_body or "",
            status_code=exc.status_code,
            media_type="application/json"
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        raw_errors = exc.errors()
        clean_errors = []
        for err in raw_errors:
            if "ctx" in err and isinstance(err["ctx"], dict):
                ctx = {}
                for k, v in err["ctx"].items():
                    if isinstance(v, Exception):
                        ctx[k] = str(v)
                    else:
                        ctx[k] = v
                err = dict(err, ctx=ctx)
            clean_errors.append(err)
        details = {"errors": clean_errors}
        return JSONResponse(
            status_code=422,
            content=error_response("Validation failed", "VALIDATION_ERROR", details)
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        error_code = "HTTP_ERROR"
        if exc.status_code == 401:
            error_code = "UNAUTHORIZED"
        elif exc.status_code == 403:
            error_code = "FORBIDDEN"
        elif exc.status_code == 404:
            error_code = "NOT_FOUND"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(exc.detail, error_code)
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content=error_response("Internal server error", "INTERNAL_SERVER_ERROR")
        )
