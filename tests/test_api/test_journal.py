"""L3 progress_journal API tests."""
from fastapi.testclient import TestClient


def test_list_and_create_journal(operator_client: TestClient, ent01):
    pid = ent01["project_id"]
    tid = 18

    r = operator_client.get(f"/api/ops/projects/{pid}/journal")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    r = operator_client.post(
        f"/api/ops/projects/{pid}/tasks/{tid}/journal",
        json={
            "week_start": "2026-07-20",
            "week_label": "7月20日-7月26日",
            "note": "pytest 周记一条",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["task_id"] == tid
    assert body["week_start"] == "2026-07-20"
    assert body["note"] == "pytest 周记一条"
    assert body["source"] == "web"

    r2 = operator_client.get(f"/api/ops/projects/{pid}/tasks/{tid}/journal")
    assert r2.status_code == 200
    assert any(j["note"] == "pytest 周记一条" for j in r2.json())

    # duplicate same week+note → 409
    r3 = operator_client.post(
        f"/api/ops/projects/{pid}/tasks/{tid}/journal",
        json={
            "week_start": "2026-07-20",
            "note": "pytest 周记一条",
        },
    )
    assert r3.status_code == 409


def test_viewer_cannot_create_journal(viewer_client: TestClient):
    r = viewer_client.post(
        "/api/ops/projects/1/tasks/18/journal",
        json={"week_start": "2026-07-21", "note": "不应写入"},
    )
    assert r.status_code == 403


def test_journal_bad_week(operator_client: TestClient, ent01):
    pid = ent01["project_id"]
    r = operator_client.post(
        f"/api/ops/projects/{pid}/tasks/18/journal",
        json={"week_start": "not-a-date", "note": "x"},
    )
    assert r.status_code == 400
