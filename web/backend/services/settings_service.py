"""系统设置服务 — 周报异常判定规则等。"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from models import AppSetting
from schemas import JournalAlertSettings

JOURNAL_ALERT_KEY = "journal_alert"

ALLOWED_STATUSES = ("未开始", "进行中", "卡点", "已完成", "已退园")
ALLOWED_MODES = ("calendar_weeks", "rolling_days")

DEFAULT_JOURNAL_ALERT = JournalAlertSettings(
    enabled=True,
    statuses=["进行中"],
    mode="calendar_weeks",
    threshold=1,
    count_missing=True,
)


def default_journal_alert() -> JournalAlertSettings:
    return DEFAULT_JOURNAL_ALERT.model_copy(deep=True)


def _parse(raw: str | None) -> JournalAlertSettings:
    if not raw:
        return default_journal_alert()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return default_journal_alert()
    try:
        return JournalAlertSettings.model_validate(data)
    except Exception:
        return default_journal_alert()


def get_journal_alert(db: Session) -> JournalAlertSettings:
    row = db.get(AppSetting, JOURNAL_ALERT_KEY)
    if row is None:
        return default_journal_alert()
    return _parse(row.value_json)


def put_journal_alert(
    db: Session,
    body: JournalAlertSettings,
    *,
    actor: str,
) -> JournalAlertSettings:
    cleaned = _normalize(body)
    payload = cleaned.model_dump()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = db.get(AppSetting, JOURNAL_ALERT_KEY)
    if row is None:
        row = AppSetting(
            setting_key=JOURNAL_ALERT_KEY,
            value_json=json.dumps(payload, ensure_ascii=False),
            updated_at=now,
            updated_by=actor,
        )
        db.add(row)
    else:
        row.value_json = json.dumps(payload, ensure_ascii=False)
        row.updated_at = now
        row.updated_by = actor
    db.commit()
    return cleaned


def _normalize(body: JournalAlertSettings) -> JournalAlertSettings:
    statuses = [s for s in body.statuses if s in ALLOWED_STATUSES]
    if not statuses:
        statuses = list(DEFAULT_JOURNAL_ALERT.statuses)
    mode = body.mode if body.mode in ALLOWED_MODES else DEFAULT_JOURNAL_ALERT.mode
    threshold = max(0, int(body.threshold))
    if mode == "rolling_days":
        threshold = max(1, threshold)
    return JournalAlertSettings(
        enabled=bool(body.enabled),
        statuses=statuses,
        mode=mode,  # type: ignore[arg-type]
        threshold=threshold,
        count_missing=bool(body.count_missing),
    )


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def is_journal_stalled(
    *,
    project_status: str,
    last_week: str | None,
    rule: JournalAlertSettings,
    today: date | None = None,
) -> bool:
    """按配置判定项目是否「周报异常」。"""
    if not rule.enabled:
        return False
    if project_status not in rule.statuses:
        return False
    if last_week is None:
        return bool(rule.count_missing)

    today = today or date.today()
    try:
        last = date.fromisoformat(str(last_week)[:10])
    except ValueError:
        return bool(rule.count_missing)

    if rule.mode == "calendar_weeks":
        # threshold=0 → 必须覆盖本周；1 → 上周或本周即可
        cutoff = monday_of(today) - timedelta(weeks=rule.threshold)
        return last < cutoff

    # rolling_days：最近周报距今超过 threshold 天
    cutoff = today - timedelta(days=rule.threshold)
    return last < cutoff


def journal_alert_label(rule: JournalAlertSettings) -> str:
    if not rule.enabled:
        return "已关闭"
    if rule.mode == "calendar_weeks":
        return f"自然周 · 落后{rule.threshold}周"
    return f"滚动 · {rule.threshold}天"
