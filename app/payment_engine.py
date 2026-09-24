from datetime import datetime, timedelta
import random
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.audit import log_audit

# Short demo intervals make recurring execution visible during local testing.
DEMO_INTERVALS = {
    "DAILY": timedelta(seconds=10),
    "WEEKLY": timedelta(seconds=20),
    "MONTHLY": timedelta(seconds=30),
}

MAX_RETRIES = 3
FAILURE_REASONS = [
    "Insufficient Balance",
    "UPI Timeout",
    "Bank Server Down",
    "Card Expired",
    "Network Error",
]


def next_execution_time(mandate: models.Mandate) -> datetime:
    """Return the next scheduled timestamp for the demo frequency."""
    if mandate.frequency not in DEMO_INTERVALS:
        raise ValueError(f"Unsupported frequency: {mandate.frequency}")
    return mandate.next_execution + DEMO_INTERVALS[mandate.frequency]


def execute_payment(
    mandate_id: int,
    db: Session,
    *,
    idempotency_key: str | None = None,
    retry_count: int = 0,
) -> models.Transaction:
    """Execute one payment attempt with idempotency protection."""
    key = idempotency_key or f"manual-{uuid4()}"

    existing = (
        db.query(models.Transaction)
        .filter(models.Transaction.idempotency_key == key)
        .first()
    )
    if existing:
        return existing

    mandate = (
        db.query(models.Mandate)
        .filter(models.Mandate.id == mandate_id)
        .first()
    )

    if not mandate:
        raise ValueError("Mandate not found")
    if mandate.status == "PAUSED":
        raise ValueError("Mandate is paused")
    if mandate.status == "CANCELLED":
        raise ValueError("Mandate is cancelled")
    if mandate.status != "ACTIVE":
        raise ValueError("Mandate is not active")

    success = random.random() < 0.90

    transaction = models.Transaction(
        transaction_id=str(uuid4()),
        mandate_id=mandate.id,
        amount=mandate.amount,
        status="SUCCESS" if success else "FAILED",
        failure_reason=None if success else random.choice(FAILURE_REASONS),
        retry_count=retry_count,
        idempotency_key=key,
    )
    db.add(transaction)

    if success:
        mandate.last_execution = mandate.next_execution
        mandate.next_execution = next_execution_time(mandate)
        log_audit(
            db,
            entity_type="TRANSACTION",
            entity_id=transaction.transaction_id,
            action="PAYMENT_SUCCEEDED",
            details=(
                f"Mandate {mandate.id}; amount={mandate.amount}; "
                f"retry_count={retry_count}"
            ),
        )
    else:
        log_audit(
            db,
            entity_type="TRANSACTION",
            entity_id=transaction.transaction_id,
            action="PAYMENT_FAILED",
            details=(
                f"Mandate {mandate.id}; reason={transaction.failure_reason}; "
                f"retry_count={retry_count}"
            ),
        )

    try:
        db.commit()
        db.refresh(transaction)
        return transaction
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(models.Transaction)
            .filter(models.Transaction.idempotency_key == key)
            .first()
        )
        if existing:
            return existing
        raise


def retry_failed_transaction(
    transaction_id: int,
    db: Session,
) -> models.Transaction:
    transaction = (
        db.query(models.Transaction)
        .filter(models.Transaction.id == transaction_id)
        .first()
    )
    if not transaction:
        raise ValueError("Transaction not found")
    if transaction.status == "SUCCESS":
        raise ValueError("Transaction already successful")
    if transaction.retry_count >= MAX_RETRIES:
        raise ValueError(f"Maximum retry limit of {MAX_RETRIES} reached")

    return execute_payment(
        transaction.mandate_id,
        db,
        idempotency_key=f"retry-{transaction.id}-{uuid4()}",
        retry_count=transaction.retry_count + 1,
    )
