from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.audit import log_audit
from app.database import get_db
from app.schemas import MandateCreate, MandateRead

router = APIRouter(tags=["Mandates"])


@router.post("/mandates", response_model=MandateRead, status_code=201)
def create_mandate(mandate: MandateCreate, db: Session = Depends(get_db)):
    new_mandate = models.Mandate(
        customer_name=mandate.customer_name,
        merchant_name=mandate.merchant_name,
        amount=mandate.amount,
        frequency=mandate.frequency,
        status="ACTIVE",
    )
    db.add(new_mandate)
    db.flush()

    log_audit(
        db,
        entity_type="MANDATE",
        entity_id=new_mandate.id,
        action="MANDATE_CREATED",
        details=(
            f"customer={new_mandate.customer_name}; "
            f"merchant={new_mandate.merchant_name}; "
            f"amount={new_mandate.amount}; frequency={new_mandate.frequency}"
        ),
    )

    db.commit()
    db.refresh(new_mandate)
    return new_mandate


@router.get("/mandates", response_model=list[MandateRead])
def get_all_mandates(db: Session = Depends(get_db)):
    return db.query(models.Mandate).order_by(models.Mandate.id.desc()).all()


@router.get("/mandates/{mandate_id}", response_model=MandateRead)
def get_mandate(mandate_id: int, db: Session = Depends(get_db)):
    mandate = db.query(models.Mandate).filter(models.Mandate.id == mandate_id).first()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found")
    return mandate


def _get_mandate_or_404(mandate_id: int, db: Session) -> models.Mandate:
    mandate = db.query(models.Mandate).filter(models.Mandate.id == mandate_id).first()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found")
    return mandate


@router.post("/mandates/{mandate_id}/pause", response_model=MandateRead)
def pause_mandate(mandate_id: int, db: Session = Depends(get_db)):
    mandate = _get_mandate_or_404(mandate_id, db)
    if mandate.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Only ACTIVE mandates can be paused")

    mandate.status = "PAUSED"
    log_audit(
        db,
        entity_type="MANDATE",
        entity_id=mandate.id,
        action="MANDATE_PAUSED",
    )
    db.commit()
    db.refresh(mandate)
    return mandate


@router.post("/mandates/{mandate_id}/resume", response_model=MandateRead)
def resume_mandate(mandate_id: int, db: Session = Depends(get_db)):
    mandate = _get_mandate_or_404(mandate_id, db)
    if mandate.status != "PAUSED":
        raise HTTPException(status_code=409, detail="Only PAUSED mandates can be resumed")

    mandate.status = "ACTIVE"
    if mandate.next_execution <= models.utcnow():
        mandate.next_execution = models.utcnow()

    log_audit(
        db,
        entity_type="MANDATE",
        entity_id=mandate.id,
        action="MANDATE_RESUMED",
    )
    db.commit()
    db.refresh(mandate)
    return mandate


@router.post("/mandates/{mandate_id}/cancel", response_model=MandateRead)
def cancel_mandate(mandate_id: int, db: Session = Depends(get_db)):
    mandate = _get_mandate_or_404(mandate_id, db)
    if mandate.status == "CANCELLED":
        raise HTTPException(status_code=409, detail="Mandate is already cancelled")

    mandate.status = "CANCELLED"
    log_audit(
        db,
        entity_type="MANDATE",
        entity_id=mandate.id,
        action="MANDATE_CANCELLED",
    )
    db.commit()
    db.refresh(mandate)
    return mandate
