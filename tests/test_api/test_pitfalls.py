"""Phase C pitfalls tests — operator_client (session cookie)."""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEST_DB = ROOT / "data" / "test_api.db"

STAGE = "厂房改造项目前期审批准备"


def test_create_and_get_pitfall(operator_client):
    response = operator_client.post(
        "/api/ops/pitfalls",
        json={
            "stage_ref": STAGE,
            "wrong_action": "pytest 错误做法",
            "right_action": "pytest 合规做法",
            "standard_ref": "测试依据",
            "impact_level": "高",
            "trigger_condition": "测试触发",
            "remediation": "测试补救",
            "notes": "pytest",
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()
    pid = created["pitfall_id"]
    assert created["stage_ref"] == STAGE

    detail = operator_client.get(f"/api/ops/pitfalls/{pid}")
    assert detail.status_code == 200
    assert detail.json()["impact_level"] == "高"

    stage_pitfalls = operator_client.get("/api/ops/stages/3/pitfalls")
    assert any(p["pitfall_id"] == pid for p in stage_pitfalls.json())

    # Clean up
    conn = sqlite3.connect(TEST_DB)
    conn.execute("DELETE FROM stage_pitfall_ref WHERE pitfall_id=?", (pid,))
    conn.execute("DELETE FROM pitfall_guide WHERE pitfall_id=?", (pid,))
    conn.commit()
    conn.close()


def test_create_pitfall_invalid_stage(operator_client):
    response = operator_client.post(
        "/api/ops/pitfalls",
        json={
            "stage_ref": "不存在的阶段",
            "wrong_action": "错误",
            "right_action": "正确",
        },
    )
    assert response.status_code == 400


def test_create_pitfall_minimal(operator_client):
    """Minimal valid pitfall payload."""
    response = operator_client.post(
        "/api/ops/pitfalls",
        json={"stage_ref": STAGE, "wrong_action": "错", "right_action": "对"},
    )
    assert response.status_code == 201
