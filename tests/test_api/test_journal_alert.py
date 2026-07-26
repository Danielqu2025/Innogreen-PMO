"""Journal alert settings + stall rule."""
from datetime import date

from fastapi.testclient import TestClient

from schemas import JournalAlertSettings
from services.settings_service import is_journal_stalled, journal_alert_label


def test_is_journal_stalled_calendar_weeks():
    rule = JournalAlertSettings(
        enabled=True,
        statuses=["进行中"],
        mode="calendar_weeks",
        threshold=1,
        count_missing=True,
    )
    # 2026-07-26 is Sunday → Monday of week is 2026-07-20
    today = date(2026, 7, 26)
    assert is_journal_stalled(
        project_status="进行中",
        last_week=None,
        rule=rule,
        today=today,
    )
    # this week OK
    assert not is_journal_stalled(
        project_status="进行中",
        last_week="2026-07-20",
        rule=rule,
        today=today,
    )
    # last week OK when threshold=1
    assert not is_journal_stalled(
        project_status="进行中",
        last_week="2026-07-13",
        rule=rule,
        today=today,
    )
    # two weeks ago NOT OK
    assert is_journal_stalled(
        project_status="进行中",
        last_week="2026-07-06",
        rule=rule,
        today=today,
    )
    # wrong status ignored
    assert not is_journal_stalled(
        project_status="已完成",
        last_week=None,
        rule=rule,
        today=today,
    )


def test_is_journal_stalled_rolling_days():
    rule = JournalAlertSettings(
        enabled=True,
        statuses=["进行中"],
        mode="rolling_days",
        threshold=14,
        count_missing=False,
    )
    today = date(2026, 7, 26)
    assert not is_journal_stalled(
        project_status="进行中",
        last_week=None,
        rule=rule,
        today=today,
    )
    assert is_journal_stalled(
        project_status="进行中",
        last_week="2026-07-01",
        rule=rule,
        today=today,
    )
    assert not is_journal_stalled(
        project_status="进行中",
        last_week="2026-07-20",
        rule=rule,
        today=today,
    )


def test_journal_alert_get_default(viewer_client: TestClient):
    r = viewer_client.get("/api/ops/settings/journal-alert")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["mode"] == "calendar_weeks"
    assert body["threshold"] == 1
    assert "进行中" in body["statuses"]
    assert body["label"]


def test_journal_alert_put_forbidden_for_operator(operator_client: TestClient):
    forbidden = operator_client.put(
        "/api/ops/settings/journal-alert",
        json={
            "enabled": True,
            "statuses": ["进行中", "卡点"],
            "mode": "rolling_days",
            "threshold": 21,
            "count_missing": True,
        },
    )
    assert forbidden.status_code == 403


def test_journal_alert_put_admin(admin_client: TestClient):
    ok = admin_client.put(
        "/api/ops/settings/journal-alert",
        json={
            "enabled": True,
            "statuses": ["进行中", "卡点"],
            "mode": "rolling_days",
            "threshold": 21,
            "count_missing": True,
        },
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["mode"] == "rolling_days"
    assert body["threshold"] == 21
    assert set(body["statuses"]) == {"进行中", "卡点"}
    assert body["label"] == journal_alert_label(
        JournalAlertSettings.model_validate(body)
    )

    # restore default for other tests
    admin_client.put(
        "/api/ops/settings/journal-alert",
        json={
            "enabled": True,
            "statuses": ["进行中"],
            "mode": "calendar_weeks",
            "threshold": 1,
            "count_missing": True,
        },
    )


def test_dashboard_includes_journal_alert(viewer_client: TestClient):
    r = viewer_client.get("/api/ops/dashboard/summary")
    assert r.status_code == 200
    alert = r.json()["journal_alert"]
    assert alert["mode"] in {"calendar_weeks", "rolling_days"}
    assert "label" in alert
