"""审计日志服务"""
import json
from datetime import datetime

from sqlalchemy.orm import Session

from models import AuditLog


def log_action(
    db: Session,
    actor: str,
    action: str,
    resource: str,
    resource_id: int | None = None,
    payload: dict | None = None,
    ip_address: str | None = None,
) -> int:
    """记录操作到 audit_log 表，返回 audit_id。"""
    audit = AuditLog(
        actor=actor,
        action=action,
        resource=resource,
        resource_id=resource_id,
        payload=json.dumps(payload, ensure_ascii=False) if payload else None,
        ip_address=ip_address,
        created_at=datetime.now().isoformat(),
    )
    db.add(audit)
    db.flush()
    return audit.audit_id
