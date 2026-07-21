"""
审计日志服务 - Phase C
记录所有写操作，便于运营追溯和合规审计
"""
import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from models import AuditLog


def log_action(
    db: Session,
    actor: str,
    action: str,  # CREATE / UPDATE / DELETE
    resource: str,  # projects / tasks / pitfalls / progress
    resource_id: int | None = None,
    payload: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> int:
    """
    记录操作到 audit_log 表。
    返回 audit_id。
    """
    audit = AuditLog(
        actor=actor,
        action=action,
        resource=resource,
        resource_id=resource_id,
        payload=json.dumps(payload, ensure_ascii=False) if payload else None,
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=datetime.now().isoformat(),
    )
    db.add(audit)
    db.flush()
    return audit.audit_id


def log_project_create(
    db: Session,
    actor: str,
    project_id: int,
    data: dict,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> int:
    """记录创建企业"""
    return log_action(
        db, actor, "CREATE", "projects", project_id, payload=data,
        ip_address=ip_address, user_agent=user_agent,
    )


def log_project_update(
    db: Session,
    actor: str,
    project_id: int,
    before: dict,
    after: dict,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> int:
    """记录更新企业"""
    return log_action(
        db, actor, "UPDATE", "projects", project_id,
        payload={"before": before, "after": after},
        ip_address=ip_address, user_agent=user_agent,
    )


def log_progress_update(
    db: Session,
    actor: str,
    project_id: int,
    task_id: int,
    before: dict | None = None,
    after: dict | None = None,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> int:
    """记录更新进度"""
    return log_action(
        db, actor, "UPDATE", "progress",
        payload={"project_id": project_id, "task_id": task_id, "before": before, "after": after},
        ip_address=ip_address, user_agent=user_agent,
    )


def log_pitfall_create(
    db: Session,
    actor: str,
    pitfall_id: int,
    data: dict,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> int:
    """记录创建避坑"""
    return log_action(
        db, actor, "CREATE", "pitfalls", pitfall_id, payload=data,
        ip_address=ip_address, user_agent=user_agent,
    )


def log_user_create(
    db: Session,
    actor: str,
    user_id: int,
    data: dict,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> int:
    """记录创建用户"""
    return log_action(
        db, actor, "CREATE", "users", user_id, payload=data,
        ip_address=ip_address, user_agent=user_agent,
    )


def log_user_update(
    db: Session,
    actor: str,
    user_id: int,
    before: dict,
    after: dict,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> int:
    """记录更新用户（角色/启用状态等；不含密码明文）"""
    return log_action(
        db, actor, "UPDATE", "users", user_id,
        payload={"before": before, "after": after},
        ip_address=ip_address, user_agent=user_agent,
    )
