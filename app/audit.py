from sqlalchemy.orm import Session

from app import models


def log_audit(
    db: Session,
    *,
    entity_type: str,
    entity_id: str | int,
    action: str,
    details: str | None = None,
) -> models.AuditLog:
    entry = models.AuditLog(
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        details=details,
    )
    db.add(entry)
    return entry
