from datetime import timedelta

from app import models
from app.payment_engine import execute_payment, retry_failed_transaction


def create_mandate(db):
    mandate = models.Mandate(
        customer_name="Test Customer",
        merchant_name="Test Merchant",
        amount=1000,
        frequency="DAILY",
        status="ACTIVE",
    )
    db.add(mandate)
    db.commit()
    db.refresh(mandate)
    return mandate


def test_successful_payment_updates_schedule(db_session, monkeypatch):
    mandate = create_mandate(db_session)
    original_next = mandate.next_execution
    monkeypatch.setattr("app.payment_engine.random.random", lambda: 0.1)

    transaction = execute_payment(
        mandate.id,
        db_session,
        idempotency_key="test-success-1",
    )

    db_session.refresh(mandate)
    assert transaction.status == "SUCCESS"
    assert transaction.transaction_id
    assert mandate.last_execution == original_next
    assert mandate.next_execution == original_next + timedelta(seconds=10)


def test_duplicate_idempotency_key_returns_same_transaction(db_session, monkeypatch):
    mandate = create_mandate(db_session)
    monkeypatch.setattr("app.payment_engine.random.random", lambda: 0.1)

    first = execute_payment(mandate.id, db_session, idempotency_key="duplicate-key")
    second = execute_payment(mandate.id, db_session, idempotency_key="duplicate-key")

    assert first.id == second.id
    assert db_session.query(models.Transaction).count() == 1


def test_failed_payment_is_recorded_without_advancing_schedule(db_session, monkeypatch):
    mandate = create_mandate(db_session)
    original_next = mandate.next_execution
    monkeypatch.setattr("app.payment_engine.random.random", lambda: 0.99)
    monkeypatch.setattr("app.payment_engine.random.choice", lambda items: items[0])

    transaction = execute_payment(
        mandate.id,
        db_session,
        idempotency_key="test-failure-1",
    )

    db_session.refresh(mandate)
    assert transaction.status == "FAILED"
    assert transaction.failure_reason == "Insufficient Balance"
    assert mandate.next_execution == original_next


def test_retry_creates_new_attempt_and_increments_retry_count(db_session, monkeypatch):
    mandate = create_mandate(db_session)
    monkeypatch.setattr("app.payment_engine.random.random", lambda: 0.99)
    failed = execute_payment(mandate.id, db_session, idempotency_key="first-failure")

    monkeypatch.setattr("app.payment_engine.random.random", lambda: 0.1)
    retried = retry_failed_transaction(failed.id, db_session)

    assert failed.status == "FAILED"
    assert retried.status == "SUCCESS"
    assert retried.retry_count == 1
    assert retried.id != failed.id
