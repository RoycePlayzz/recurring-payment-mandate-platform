from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.payment_engine import execute_payment, retry_failed_transaction
from app.schemas import AuditRead, TransactionRead

router = APIRouter(tags=["Payments & Analytics"])


@router.post("/payments/execute/{mandate_id}", response_model=TransactionRead)
def execute_payment_api(
    mandate_id: int,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
):
    try:
        return execute_payment(
            mandate_id,
            db,
            idempotency_key=idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/transactions/{transaction_id}/retry", response_model=TransactionRead)
def retry_transaction(transaction_id: int, db: Session = Depends(get_db)):
    try:
        return retry_failed_transaction(transaction_id, db)
    except ValueError as exc:
        status_code = 404 if str(exc) == "Transaction not found" else 409
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/transactions", response_model=list[TransactionRead])
def get_all_transactions(db: Session = Depends(get_db)):
    return (
        db.query(models.Transaction)
        .order_by(models.Transaction.id.desc())
        .limit(100)
        .all()
    )


@router.get("/transactions/{transaction_id}", response_model=TransactionRead)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    transaction = (
        db.query(models.Transaction)
        .filter(models.Transaction.id == transaction_id)
        .first()
    )
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    active = db.query(models.Mandate).filter(models.Mandate.status == "ACTIVE").count()
    paused = db.query(models.Mandate).filter(models.Mandate.status == "PAUSED").count()
    cancelled = db.query(models.Mandate).filter(models.Mandate.status == "CANCELLED").count()

    transaction_count = db.query(models.Transaction).count()
    success_count = (
        db.query(models.Transaction)
        .filter(models.Transaction.status == "SUCCESS")
        .count()
    )
    failed_count = (
        db.query(models.Transaction)
        .filter(models.Transaction.status == "FAILED")
        .count()
    )
    revenue = (
        db.query(func.coalesce(func.sum(models.Transaction.amount), 0))
        .filter(models.Transaction.status == "SUCCESS")
        .scalar()
    ) or 0

    return {
        "active": active,
        "paused": paused,
        "cancelled": cancelled,
        "transactions": transaction_count,
        "revenue": int(revenue),
        "success": success_count,
        "failed": failed_count,
        "success_rate": round((success_count / transaction_count) * 100, 2)
        if transaction_count
        else 0,
    }


@router.get("/merchant-analytics")
def merchant_analytics(db: Session = Depends(get_db)):
    success_case = case((models.Transaction.status == "SUCCESS", 1), else_=0)
    failed_case = case((models.Transaction.status == "FAILED", 1), else_=0)
    success_revenue_case = case(
        (models.Transaction.status == "SUCCESS", models.Transaction.amount),
        else_=0,
    )

    rows = (
        db.query(
            models.Mandate.merchant_name.label("merchant"),
            func.coalesce(func.sum(success_revenue_case), 0).label("revenue"),
            func.sum(success_case).label("success"),
            func.sum(failed_case).label("failed"),
            func.count(models.Transaction.id).label("total"),
        )
        .outerjoin(
            models.Transaction,
            models.Transaction.mandate_id == models.Mandate.id,
        )
        .group_by(models.Mandate.merchant_name)
        .order_by(func.coalesce(func.sum(success_revenue_case), 0).desc())
        .all()
    )

    result = []
    for row in rows:
        success = int(row.success or 0)
        failed = int(row.failed or 0)
        total = int(row.total or 0)
        result.append(
            {
                "merchant": row.merchant,
                "revenue": int(row.revenue or 0),
                "success": success,
                "failed": failed,
                "total": total,
                "success_rate": round((success / total) * 100, 2) if total else 0,
            }
        )
    return result


@router.get("/audit-logs", response_model=list[AuditRead])
def get_audit_logs(db: Session = Depends(get_db)):
    return db.query(models.AuditLog).order_by(models.AuditLog.id.desc()).limit(50).all()
