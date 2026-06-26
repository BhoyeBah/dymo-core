from typing import List, Optional
from pydantic import BaseModel, ConfigDict
import uuid

class TenantSettingResponse(BaseModel):
    id: uuid.UUID
    key: str
    value: str
    is_encrypted: bool

    model_config = ConfigDict(from_attributes=True)

class TenantSettingCreateOrUpdate(BaseModel):
    key: str
    value: str
