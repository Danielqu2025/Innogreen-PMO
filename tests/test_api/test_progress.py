"""Phase C progress tests — operator_client (session cookie)."""
from fastapi.testclient import TestClient


def test_progress_lists_l2_and_l3_for_stage(operator_client: TestClient):
    """任务进度应同时返回二级与三级（无落库行的补待开始占位）。"""
    create = operator_client.post(
        "/api/ops/projects",
        json={
            "project_code": "ENT-PY-L2L3",
            "company_name": "ENT-PY-L2L3",
            "short_name": "L23",
        },
    )
    assert create.status_code == 201
    pid = create.json()["project_id"]

    tasks = [
        t
        for t in operator_client.get("/api/ops/tasks").json()
        if t.get("is_active", 1) == 1 and t["stage_id"] == 2 and t.get("task_code")
    ]
    l2_codes = {t["task_code"] for t in tasks if t["task_code"].count(".") == 1}
    l3_codes = {t["task_code"] for t in tasks if t["task_code"].count(".") == 2}
    assert l2_codes and l3_codes

    progress = operator_client.get(f"/api/ops/projects/{pid}/progress").json()
    stage2 = [p for p in progress if p["stage_id"] == 2]
    got = {p["task_code"] for p in stage2}
    assert l2_codes <= got
    assert l3_codes <= got
    # 新项目无导入进度时，占位行 progress_id=0、status=待开始
    assert all(p["progress_id"] == 0 and p["status"] == "待开始" for p in stage2)
    # 按 task_code 可排序（与前端一致）
    codes = [p["task_code"] for p in stage2]
    assert codes == sorted(codes, key=lambda c: [int(x) for x in c.split(".")])


def test_progress_complete_sets_completed_at(operator_client: TestClient, ent01):
    pid = ent01["project_id"]
    response = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/18",
        json={"status": "已完成", "assigned_to": "李四"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "已完成"
    assert body["completed_at"] is not None

    project = operator_client.get(f"/api/ops/projects/{pid}").json()
    assert project["progress_percent"] >= ent01["project"]["progress_percent"]


def test_blocker_syncs_project_status(operator_client: TestClient, ent01):
    pid = ent01["project_id"]

    # 先 resolve 任务 19（如果它还是卡点的话）
    operator_client.put(
        f"/api/ops/projects/{pid}/tasks/19",
        json={"status": "已完成", "assigned_to": "李四"},
    )

    response = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/20",
        json={
            "status": "卡点",
            "assigned_to": "王五",
            "blocker_note": "pytest 卡点测试",
        },
    )
    assert response.status_code == 200

    project = operator_client.get(f"/api/ops/projects/{pid}").json()
    assert project["project_status"] == "卡点"
    # 卡点不再单独覆盖阶段；阶段按已触达最大阶段（此处仍为阶段 3 前期审批）
    assert project["current_stage_id"] == 3

    blockers = operator_client.get("/api/ops/progress/blockers").json()
    assert any(b["project_id"] == pid and b["task_id"] == 20 for b in blockers)


def test_resolve_blocker_restores_in_progress(operator_client: TestClient, ent01):
    pid = ent01["project_id"]
    operator_client.put(
        f"/api/ops/projects/{pid}/tasks/19",
        json={"status": "已完成", "assigned_to": "李四"},
    )
    operator_client.put(
        f"/api/ops/projects/{pid}/tasks/20",
        json={"status": "已完成", "assigned_to": "王五"},
    )

    project = operator_client.get(f"/api/ops/projects/{pid}").json()
    assert project["project_status"] == "进行中"


def test_auto_stage_advances_on_later_stage_touch(operator_client: TestClient, ent01):
    """出现下一阶段工作记录（进行中）→ 自动进入该阶段。"""
    pid = ent01["project_id"]
    assert ent01["project"]["current_stage_id"] == 3

    response = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/72",  # stage 5 施工审批
        json={"status": "进行中", "assigned_to": "测试"},
    )
    assert response.status_code == 200

    project = operator_client.get(f"/api/ops/projects/{pid}").json()
    assert project["current_stage_id"] == 5


def test_auto_stage_ignores_utility_stage(operator_client: TestClient, ent01):
    """仅有公用工程阶段进度时，不把当前阶段写成该阶段，仍停在已触达主链最大阶段。"""
    pid = ent01["project_id"]

    response = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/33",  # stage 4 公用工程
        json={"status": "进行中", "assigned_to": "测试"},
    )
    assert response.status_code == 200

    project = operator_client.get(f"/api/ops/projects/{pid}").json()
    assert project["current_stage_id"] == 3


def test_auto_stage_ignores_pending_status(operator_client: TestClient):
    """待开始不计入触达；进行中才推进阶段。"""
    create = operator_client.post(
        "/api/ops/projects",
        json={
            "project_code": "ENT-PY-STAGE",
            "company_name": "ENT-PY-STAGE",
            "short_name": "PAS",
        },
    )
    assert create.status_code == 201
    pid = create.json()["project_id"]
    assert create.json()["current_stage_id"] is None

    pending = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/4",  # stage 1
        json={"status": "待开始", "assigned_to": "测试"},
    )
    assert pending.status_code == 200
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["current_stage_id"] is None

    active = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/4",
        json={"status": "进行中", "assigned_to": "测试"},
    )
    assert active.status_code == 200
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["current_stage_id"] == 1


def test_auto_stage_advanced_unlock_skips_early_gaps(operator_client: TestClient):
    """阶段5+已触达时走旧规则：即使1/2/3空缺也前推到该阶段。"""
    create = operator_client.post(
        "/api/ops/projects",
        json={
            "project_code": "ENT-PY-ADV",
            "company_name": "ENT-PY-ADV",
            "short_name": "ADV",
        },
    )
    assert create.status_code == 201
    pid = create.json()["project_id"]

    r = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/72",  # stage 5，跳过1/2/3
        json={"status": "进行中", "assigned_to": "测试"},
    )
    assert r.status_code == 200
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["current_stage_id"] == 5


def test_auto_stage_early_clamp_before_unstarted_linear(operator_client: TestClient):
    """5–8未开始：阶段2空缺时，即使阶段3有记录，也只能算到阶段2之前。"""
    create = operator_client.post(
        "/api/ops/projects",
        json={
            "project_code": "ENT-PY-CLAMP",
            "company_name": "ENT-PY-CLAMP",
            "short_name": "CLP",
        },
    )
    assert create.status_code == 201
    pid = create.json()["project_id"]

    # 仅阶段3有记录、阶段1未开始 → 只能算到阶段0
    only3 = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/18",  # stage 3
        json={"status": "进行中", "assigned_to": "测试"},
    )
    assert only3.status_code == 200
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["current_stage_id"] == 0

    # 补阶段1后，阶段2仍空 → 当前=阶段1（阶段2之前）
    s1 = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/4",  # stage 1
        json={"status": "已完成", "assigned_to": "测试"},
    )
    assert s1.status_code == 200
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["current_stage_id"] == 1


def test_auto_stage_stage1_missing_is_zero(operator_client: TestClient):
    """5–8未开始且阶段1未触达：即使阶段2有记录，当前阶段=0。"""
    create = operator_client.post(
        "/api/ops/projects",
        json={
            "project_code": "ENT-PY-S0",
            "company_name": "ENT-PY-S0",
            "short_name": "S0",
        },
    )
    assert create.status_code == 201
    pid = create.json()["project_id"]

    r = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/6",  # stage 2，跳过阶段1
        json={"status": "进行中", "assigned_to": "测试"},
    )
    assert r.status_code == 200
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["current_stage_id"] == 0


def test_read_paths_refresh_stale_current_stage(operator_client: TestClient):
    """列表/详情/看板读路径应纠正过期的 current_stage_id（无需再写进度）。"""
    import sqlite3

    from conftest import TEST_DB

    create = operator_client.post(
        "/api/ops/projects",
        json={
            "project_code": "ENT-PY-STALE",
            "company_name": "ENT-PY-STALE",
            "short_name": "STL",
        },
    )
    assert create.status_code == 201
    pid = create.json()["project_id"]

    r = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/72",  # stage 5
        json={"status": "进行中", "assigned_to": "测试"},
    )
    assert r.status_code == 200
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["current_stage_id"] == 5

    # 模拟算法升级前残留的过期缓存
    conn = sqlite3.connect(TEST_DB)
    conn.execute(
        "UPDATE project_profile SET current_stage_id=1 WHERE project_id=?",
        (pid,),
    )
    conn.commit()
    conn.close()

    detail = operator_client.get(f"/api/ops/projects/{pid}").json()
    assert detail["current_stage_id"] == 5

    listed = operator_client.get("/api/ops/projects").json()
    row = next(p for p in listed if p["project_id"] == pid)
    assert row["current_stage_id"] == 5

    dash = operator_client.get("/api/ops/dashboard/summary").json()
    drow = next(p for p in dash["projects"] if p["project_id"] == pid)
    assert drow["current_stage_id"] == 5

    conn = sqlite3.connect(TEST_DB)
    cached = conn.execute(
        "SELECT current_stage_id FROM project_profile WHERE project_id=?",
        (pid,),
    ).fetchone()[0]
    conn.close()
    assert cached == 5


def test_progress_invalid_status(operator_client: TestClient, ent01):
    pid = ent01["project_id"]
    response = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/18",
        json={"status": "无效状态"},
    )
    assert response.status_code == 400


def test_critical_path_for_project(operator_client: TestClient, ent01):
    pid = ent01["project_id"]
    response = operator_client.get(f"/api/ops/projects/{pid}/critical-path")
    assert response.status_code == 200
    body = response.json()
    assert body["project_code"] == "ENT-01"
    assert len(body["nodes"]) > 0


def _active_task_count(client: TestClient, *, stage_id: int | None = None, exclude_stage0: bool = False) -> int:
    """通过任务目录接口统计启用任务数。"""
    tasks = client.get("/api/ops/tasks").json()
    rows = [t for t in tasks if t.get("is_active", 1) == 1]
    if exclude_stage0:
        rows = [t for t in rows if t["stage_id"] != 0]
    if stage_id is not None:
        rows = [t for t in rows if t["stage_id"] == stage_id]
    return len(rows)


def _base_denom(client: TestClient) -> int:
    """进度分母中非阶段4部分：启用且 stage∉{0,4}。"""
    tasks = client.get("/api/ops/tasks").json()
    return sum(
        1
        for t in tasks
        if t.get("is_active", 1) == 1 and t["stage_id"] not in (0, 4)
    )


def _project_denom(client: TestClient, pid: int) -> int:
    """项目进度分母：base + 阶段4在册且非已跳过。"""
    progress = client.get(f"/api/ops/projects/{pid}/progress").json()
    # progress_id=0 为未落库占位，不算「在册」
    stage4_in_scope = sum(
        1
        for p in progress
        if p["stage_id"] == 4 and p.get("progress_id") and p["status"] != "已跳过"
    )
    return _base_denom(client) + stage4_in_scope


def test_progress_excludes_stage0_and_pending(operator_client: TestClient):
    """阶段0与待开始不计入；仅触达线性阶段1时分子=触达任务数。"""
    create = operator_client.post(
        "/api/ops/projects",
        json={
            "project_code": "ENT-PY-PCT0",
            "company_name": "ENT-PY-PCT0",
            "short_name": "P0",
        },
    )
    assert create.status_code == 201
    pid = create.json()["project_id"]
    denom = _project_denom(operator_client, pid)
    assert denom > 0

    # 阶段0任务触达：不应增加进度
    stage0 = next(
        t for t in operator_client.get("/api/ops/tasks").json()
        if t["stage_id"] == 0 and t.get("is_active", 1) == 1
    )
    r0 = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/{stage0['task_id']}",
        json={"status": "已完成", "assigned_to": "测试"},
    )
    assert r0.status_code == 200
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["progress_percent"] == 0

    # 待开始不算触达
    pending = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/4",  # stage 1
        json={"status": "待开始", "assigned_to": "测试"},
    )
    assert pending.status_code == 200
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["progress_percent"] == 0

    active = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/4",
        json={"status": "进行中", "assigned_to": "测试"},
    )
    assert active.status_code == 200
    # 进行中权重 0.5
    expected = round(100 * 0.5 / denom)
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["progress_percent"] == expected

    done = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/4",
        json={"status": "已完成", "assigned_to": "测试"},
    )
    assert done.status_code == 200
    expected_done = round(100 * 1 / denom)
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["progress_percent"] == expected_done


def test_progress_linear_auto_completes_prior_stages(operator_client: TestClient):
    """触达阶段5时：线性前序1+2 + 阶段3 全部自动完成。"""
    create = operator_client.post(
        "/api/ops/projects",
        json={
            "project_code": "ENT-PY-LIN",
            "company_name": "ENT-PY-LIN",
            "short_name": "PL",
        },
    )
    assert create.status_code == 201
    pid = create.json()["project_id"]
    s1 = _active_task_count(operator_client, stage_id=1)
    s2 = _active_task_count(operator_client, stage_id=2)
    s3 = _active_task_count(operator_client, stage_id=3)

    r = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/72",  # stage 5
        json={"status": "进行中", "assigned_to": "测试"},
    )
    assert r.status_code == 200

    denom = _project_denom(operator_client, pid)
    # 前序线性 1+2 + 阶段3 全完成(各1) + 阶段5进行中(0.5)；阶段4无记录不入分母
    expected = round(100 * (s1 + s2 + s3 + 0.5) / denom)
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["progress_percent"] == expected


def test_progress_parallel_counts_touched_only(operator_client: TestClient):
    """并行阶段4：仅在册非已跳过计入分母；不触发线性前序。"""
    create = operator_client.post(
        "/api/ops/projects",
        json={
            "project_code": "ENT-PY-PAR",
            "company_name": "ENT-PY-PAR",
            "short_name": "PP",
        },
    )
    assert create.status_code == 201
    pid = create.json()["project_id"]

    r = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/33",  # stage 4 公用工程
        json={"status": "进行中", "assigned_to": "测试"},
    )
    assert r.status_code == 200
    denom = _project_denom(operator_client, pid)
    # 仅并行进行中 0.5；缺失的阶段4事项不入分母
    expected = round(100 * 0.5 / denom)
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["progress_percent"] == expected

    # 再触达线性阶段2(已完成=1)：前序阶段1自动完成 + 阶段2触达1 + 并行进行中0.5
    s1 = _active_task_count(operator_client, stage_id=1)
    r2 = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/6",  # stage 2
        json={"status": "已完成", "assigned_to": "测试"},
    )
    assert r2.status_code == 200
    denom2 = _project_denom(operator_client, pid)
    expected2 = round(100 * (s1 + 1 + 0.5) / denom2)
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["progress_percent"] == expected2


def test_progress_stage4_skip_and_missing_excluded(operator_client: TestClient):
    """阶段4：已跳过与无记录不计入分母/分子；非阶段4的已跳过仍计权重1。"""
    create = operator_client.post(
        "/api/ops/projects",
        json={
            "project_code": "ENT-PY-S4",
            "company_name": "ENT-PY-S4",
            "short_name": "S4",
        },
    )
    assert create.status_code == 201
    pid = create.json()["project_id"]
    base = _base_denom(operator_client)

    # 阶段4仅已跳过：分母不含该条，进度仍为0
    skip4 = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/33",
        json={"status": "已跳过", "assigned_to": "测试"},
    )
    assert skip4.status_code == 200
    assert _project_denom(operator_client, pid) == base
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["progress_percent"] == 0

    # 阶段4卡点：进入分母，权重0.5
    block4 = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/34",
        json={"status": "卡点", "assigned_to": "测试", "blocker_note": "等资料"},
    )
    assert block4.status_code == 200
    denom = _project_denom(operator_client, pid)
    assert denom == base + 1
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["progress_percent"] == round(
        100 * 0.5 / denom
    )

    # 非阶段4已跳过：权重1，分母不变（仍只有1条阶段4在册）
    skip1 = operator_client.put(
        f"/api/ops/projects/{pid}/tasks/4",
        json={"status": "已跳过", "assigned_to": "测试"},
    )
    assert skip1.status_code == 200
    assert _project_denom(operator_client, pid) == denom
    assert operator_client.get(f"/api/ops/projects/{pid}").json()["progress_percent"] == round(
        100 * (0.5 + 1) / denom
    )
