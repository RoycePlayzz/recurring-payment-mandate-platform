from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal
from app.payment_engine import execute_payment

scheduler = BackgroundScheduler(timezone="UTC")


def process_payments() -> None:
    db: Session = SessionLocal()
    try:
        current_time = models.utcnow()
        mandates = (
            db.query(models.Mandate)
            .filter(
                models.Mandate.status == "ACTIVE",
                models.Mandate.next_execution <= current_time,
            )
            .all()
        )

        for mandate in mandates:
            execution_key = f"scheduler:{mandate.id}:{mandate.next_execution.isoformat()}"
            try:
                execute_payment(
                    mandate.id,
                    db,
                    idempotency_key=execution_key,
                )
            except ValueError:
                db.rollback()
    finally:
        db.close()


def start_scheduler() -> None:
    if scheduler.running:
        return

    scheduler.add_job(
        process_payments,
        trigger="interval",
        seconds=5,
        id="payment_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
