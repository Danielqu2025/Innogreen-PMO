"""Dashboard summary — three-question ops view."""
from fastapi.testclient import TestClient


def test_dashboard_summary_shape(viewer_client: TestClient):
    r = viewer_client.get("/api/ops/dashboard/summary")
    assert r.status_code == 200
    body = r.json()
    assert "total_projects" in body
    assert "by_status" in body
    assert "by_stage" in body
    assert "blockers" in body
    assert "projects" in body
    assert "delayed_tasks" in body
    assert "counts" in body
    assert "phase_buckets" in body
    assert set(body["counts"]) >= {
        "blocker_projects",
        "delayed_projects",
        "stalled_projects",
    }
    assert set(body["phase_buckets"]) >= {
        "access_projects",
        "construction_projects",
        "operation_projects",
    }
    assert all(v > 0 for v in body["by_stage"].values()) or body["by_stage"] == {}
    if body["projects"]:
        p = body["projects"][0]
        assert "flags" in p
        assert set(p["flags"]) >= {"blocker", "delayed", "stalled"}
        # 阶段从后到前；同阶段进度降序
        rows = body["projects"]
        stage_ids = [x.get("current_stage_id") if x.get("current_stage_id") is not None else -1 for x in rows]
        assert stage_ids == sorted(stage_ids, reverse=True)


def test_dashboard_lists_projects(operator_client: TestClient):
    r = operator_client.get("/api/ops/dashboard/summary")
    assert r.status_code == 200
    codes = {p["project_code"] for p in r.json()["projects"]}
    assert "ENT-01" in codes
