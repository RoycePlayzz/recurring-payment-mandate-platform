from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Frequency = Literal["DAILY", "WEEKLY", "MONTHLY"]


class MandateCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=120)
    merchant_name: str = Field(min_length=1, max_length=120)
    amount: int = Field(gt=0)
    frequency: Frequency

    model_config = ConfigDict(str_strip_whitespace=True)


class MandateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_name: str
    merchant_name: str
    amount: int
    frequency: str
    status: str
    start_date: datetime
    last_execution: datetime | None
    next_execution: datetime


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: str
    mandate_id: int
    amount: int
    status: str
    failure_reason: str | None
    retry_count: int
    idempotency_key: str
    created_at: datetime


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: str
    action: str
    details: str | None
    created_at: datetime
