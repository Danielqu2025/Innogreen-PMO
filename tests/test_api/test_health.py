def test_health_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db_exists"] is True
    # 不对外暴露绝对路径
    assert "db_path" not in body
