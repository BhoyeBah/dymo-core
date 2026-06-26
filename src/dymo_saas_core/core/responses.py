from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class BaseResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None

class PaginatedMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int

class PaginatedResponse(BaseResponse, Generic[T]):
    data: List[T]
    meta: PaginatedMeta

class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error_code: str
    details: Optional[dict] = None

def success_response(data: Any = None, message: str = "Operation successful", meta: Optional[dict] = None) -> dict:
    resp = {
        "success": True,
        "message": message,
        "data": data
    }
    if meta is not None:
        resp["meta"] = meta
    return resp

def error_response(message: str, error_code: str, details: Optional[dict] = None) -> dict:
    return {
        "success": False,
        "message": message,
        "error_code": error_code,
        "details": details or {}
    }
