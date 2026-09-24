from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text

from app.database import Base


def utcnow() -> datetime:
    """Return a naive UTC datetime for SQLite-friendly storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_transaction_id() -> str:
    return str(uuid4())


class Mandate(Base):
    __tablename__ = "mandates"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_mandates_amount_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(120), nullable=False)
    merchant_name = Column(String(120), nullable=False)
    amount = Column(Integer, nullable=False)
    frequency = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="ACTIVE")
    start_date = Column(DateTime, nullable=False, default=utcnow)
    last_execution = Column(DateTime, nullable=True)
    next_execution = Column(DateTime, nullable=False, default=utcnow)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
    )

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(
        String(36), nullable=False, unique=True, index=True, default=new_transaction_id
    )
    mandate_id = Column(Integer, ForeignKey("mandates.id"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False)  # SUCCESS / FAILED
    failure_reason = Column(String(120), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    idempotency_key = Column(String(200), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(100), nullable=False, index=True)
    action = Column(String(80), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
