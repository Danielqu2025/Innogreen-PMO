#!/usr/bin/env python3
"""
智能数据库迁移脚本 - 从源数据库迁移数据到目标数据库

功能：
1. 检测 schema 差异
2. 自动补充缺失列
3. 验证数据完整性
4. 回滚支持

用法:
    python scripts/migrate_db.py --source <源db路径> [--target <目标db路径>] [--dry-run]
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# 要迁移的表及其关键列
TABLES_TO_MIGRATE = [
    ("project_profile", ["project_id", "project_code", "company_name"]),
    ("project_progress", ["progress_id", "project_id", "task_id", "status"]),
    ("progress_journal", ["journal_id", "project_id", "task_id", "week_start"]),
]

# 必需的核心表
REQUIRED_TABLES = ["stage_map", "task_detail", "project_profile", "users"]


def get_table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """获取表的所有列名"""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def get_table_row_count(conn: sqlite3.Connection, table: str) -> int:
    """获取表的行数"""
    cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
    return cursor.fetchone()[0]


def check_database_health(conn: sqlite3.Connection) -> tuple[bool, list[str]]:
    """检查数据库健康状态"""
    errors = []

    # 检查完整性
    cursor = conn.execute("PRAGMA integrity_check")
    result = cursor.fetchone()[0]
    if result != "ok":
        errors.append(f"完整性检查失败: {result}")

    # 检查必需表
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    missing = set(REQUIRED_TABLES) - tables
    if missing:
        errors.append(f"缺少必需表: {', '.join(missing)}")

    return len(errors) == 0, errors


def analyze_schema_diff(source_conn: sqlite3.Connection, target_conn: sqlite3.Connection) -> dict:
    """分析源数据库和目标数据库的 schema 差异"""
    diff = {
        "missing_tables": [],
        "extra_tables": [],
        "missing_columns": {},
        "extra_columns": {},
        "common_tables": [],
    }

    # 获取所有表
    source_tables = set()
    target_tables = set()

    for conn, tables_set in [(source_conn, source_tables), (target_conn, target_tables)]:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        for row in cursor.fetchall():
            if row[0] not in ("sqlite_sequence",):
                tables_set.add(row[0])

    diff["missing_tables"] = list(target_tables - source_tables)
    diff["extra_tables"] = list(source_tables - target_tables)
    diff["common_tables"] = list(source_tables & target_tables)

    # 分析列差异
    for table in diff["common_tables"]:
        source_cols = set(get_table_columns(source_conn, table))
        target_cols = set(get_table_columns(target_conn, table))

        diff["missing_columns"][table] = list(target_cols - source_cols)
        diff["extra_columns"][table] = list(source_cols - target_cols)

    return diff


def add_missing_columns(conn: sqlite3.Connection, table: str, columns: list[str], defaults: dict | None = None) -> None:
    """为目标表添加缺失的列"""
    if defaults is None:
        defaults = {}

    for col in columns:
        default = defaults.get(col, "NULL")
        sql = f"ALTER TABLE {table} ADD COLUMN {col} {default}"
        try:
            conn.execute(sql)
            print(f"  [+] 添加列 {table}.{col}")
        except sqlite3.OperationalError as e:
            print(f"  [!] 添加列失败 {table}.{col}: {e}")


def migrate_table_data(
    source_conn: sqlite3.Connection,
    target_conn: sqlite3.Connection,
    table: str,
    key_columns: list[str],
    dry_run: bool = False,
) -> tuple[int, int]:
    """迁移表数据，返回 (成功数, 跳过数)"""
    if table not in [t[0] for t in TABLES_TO_MIGRATE]:
        return 0, 0

    # 获取公共列
    source_cols = set(get_table_columns(source_conn, table))
    target_cols = set(get_table_columns(target_conn, table))
    common_cols = list(source_cols & target_cols)

    if not common_cols:
        print(f"  [!] 表 {table} 没有公共列，跳过")
        return 0, 0

    # 获取关键列
    key_cols = [c for c in key_columns if c in common_cols]
    if not key_cols:
        print(f"  [!] 表 {table} 没有关键列，跳过")
        return 0, 0

    # 构建查询
    cols_str = ", ".join(common_cols)
    placeholders = ", ".join(["?" for _ in common_cols])

    # 获取源数据
    source_cursor = source_conn.execute(f"SELECT {cols_str} FROM {table}")
    rows = source_cursor.fetchall()

    success = 0
    skipped = 0

    for row in rows:
        row_dict = dict(zip(common_cols, row))
        key_values = tuple(row_dict.get(c) for c in key_cols)

        # 检查是否已存在
        if len(key_cols) == 1:
            where = f"{key_cols[0]} = ?"
        else:
            where = " AND ".join([f"{c} = ?" for c in key_cols])

        check_sql = f"SELECT COUNT(*) FROM {table} WHERE {where}"
        target_cursor = target_conn.execute(check_sql, key_values)

        if target_cursor.fetchone()[0] > 0:
            # 更新现有记录
            if not dry_run:
                set_clause = ", ".join([f"{c} = ?" for c in common_cols if c not in key_cols])
                if set_clause:
                    update_sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
                    update_values = [row_dict.get(c) for c in common_cols if c not in key_cols] + list(key_values)
                    try:
                        target_conn.execute(update_sql, update_values)
                        success += 1
                    except sqlite3.Error as e:
                        skipped += 1
                else:
                    skipped += 1
            else:
                success += 1
        else:
            # 插入新记录
            if not dry_run:
                try:
                    target_conn.execute(
                        f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders})",
                        row,
                    )
                    success += 1
                except sqlite3.Error as e:
                    print(f"    [!] 插入失败: {e}")
                    skipped += 1
            else:
                success += 1

    return success, skipped


def main():
    parser = argparse.ArgumentParser(description="智能数据库迁移工具")
    parser.add_argument("--source", required=True, help="源数据库路径")
    parser.add_argument("--target", default=None, help="目标数据库路径 (默认: data/innogreen_pmo.db)")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行，不实际写入")
    parser.add_argument("--skip-users", action="store_true", help="跳过用户表迁移")

    args = parser.parse_args()

    # 确定路径
    source_path = Path(args.source).expanduser().resolve()
    target_path = (
        Path(args.target).expanduser().resolve()
        if args.target
        else Path(__file__).parent.parent / "data" / "innogreen_pmo.db"
    )

    print("=" * 60)
    print("智能数据库迁移工具")
    print("=" * 60)
    print(f"源数据库: {source_path}")
    print(f"目标数据库: {target_path}")
    print(f"模式: {'模拟运行 (dry-run)' if args.dry_run else '实际执行'}")
    print("-" * 60)

    # 检查文件存在
    if not source_path.exists():
        print(f"[ERROR] 源数据库不存在: {source_path}")
        sys.exit(1)

    if not target_path.exists():
        print(f"[ERROR] 目标数据库不存在: {target_path}")
        sys.exit(1)

    # 连接数据库
    try:
        source_conn = sqlite3.connect(str(source_path))
        target_conn = sqlite3.connect(str(target_path))
        source_conn.row_factory = sqlite3.Row
        target_conn.row_factory = sqlite3.Row
    except sqlite3.Error as e:
        print(f"[ERROR] 无法连接数据库: {e}")
        sys.exit(1)

    # 健康检查
    print("\n[1/5] 检查数据库健康状态...")

    source_healthy, source_errors = check_database_health(source_conn)
    if not source_healthy:
        print(f"  [!] 源数据库存在问题:")
        for err in source_errors:
            print(f"      - {err}")

    target_healthy, target_errors = check_database_health(target_conn)
    if not target_healthy:
        print(f"  [!] 目标数据库存在问题:")
        for err in target_errors:
            print(f"      - {err}")

    # Schema 分析
    print("\n[2/5] 分析 Schema 差异...")

    diff = analyze_schema_diff(source_conn, target_conn)

    if diff["missing_tables"]:
        print(f"  [!] 源数据库缺少表: {', '.join(diff['missing_tables'])}")
    if diff["extra_tables"]:
        print(f"  [+] 源数据库有额外表: {', '.join(diff['extra_tables'])}")

    for table in diff["common_tables"]:
        if diff["missing_columns"].get(table):
            print(f"  [!] {table} 缺少列: {', '.join(diff['missing_columns'][table])}")
        if diff["extra_columns"].get(table):
            print(f"  [+] {table} 有额外列: {', '.join(diff['extra_columns'][table])}")

    if not any(diff["missing_columns"].values()):
        print("  [OK] Schema 完全兼容")

    # 添加缺失列
    print("\n[3/5] 补充缺失列...")

    if not args.dry_run:
        target_conn.execute("BEGIN TRANSACTION")
        try:
            for table, cols in diff["missing_columns"].items():
                if cols:
                    add_missing_columns(target_conn, table, cols)
            target_conn.commit()
        except Exception as e:
            target_conn.rollback()
            print(f"  [ERROR] 添加列失败: {e}")
            sys.exit(1)
    else:
        print("  [SKIP] 模拟运行，跳过")

    # 数据迁移
    print("\n[4/5] 迁移数据...")

    total_success = 0
    total_skipped = 0

    for table_name, key_cols in TABLES_TO_MIGRATE:
        if table_name == "users" and args.skip_users:
            print(f"\n  [SKIP] 跳过用户表")
            continue

        if table_name not in diff["common_tables"]:
            print(f"\n  [SKIP] {table_name} 不存在于目标数据库")
            continue

        print(f"\n  迁移表: {table_name}")

        source_count = get_table_row_count(source_conn, table_name)
        target_count = get_table_row_count(target_conn, table_name)
        print(f"    源数据库: {source_count} 条记录")
        print(f"    目标数据库: {target_count} 条记录")

        success, skipped = migrate_table_data(
            source_conn, target_conn, table_name, key_cols, args.dry_run
        )
        print(f"    将迁移: {success} 条")
        if skipped:
            print(f"    跳过: {skipped} 条")

        total_success += success
        total_skipped += skipped

    if not args.dry_run:
        try:
            target_conn.commit()
            print("\n  [OK] 数据迁移完成")
        except Exception as e:
            target_conn.rollback()
            print(f"\n  [ERROR] 提交失败: {e}")
            print("  [INFO] 事务已回滚")
            sys.exit(1)
    else:
        print("\n  [SIMULATED] 模拟完成")

    # 验证
    print("\n[5/5] 验证结果...")

    target_conn.commit()  # 确保能看到最新数据
    for table_name, _ in TABLES_TO_MIGRATE:
        if table_name == "users" and args.skip_users:
            continue
        if table_name in diff["common_tables"]:
            count = get_table_row_count(target_conn, table_name)
            print(f"  {table_name}: {count} 条记录")

    print("\n" + "=" * 60)
    print("迁移完成!")
    print(f"  总计迁移: {total_success} 条")
    if total_skipped:
        print(f"  总计跳过: {total_skipped} 条")
    print("=" * 60)

    source_conn.close()
    target_conn.close()


if __name__ == "__main__":
    main()
