"""
qcc 企业资质库集成服务 - 方案一（直接 ATTACH qcc 数据库只读查询）

后端通过 SQLite ATTACH DATABASE 附加 qcc/qualifications.db，
只读联查 companies / qualifications 表，填充企业工商信息和资质证照。

qcc 数据库路径通过 config.pmo_qcc_db_path 配置。
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from config import get_settings


def is_qcc_available() -> bool:
    """检查 qcc 数据库是否可访问。"""
    settings = get_settings()
    if not settings.pmo_qcc_db_path:
        return False
    import os
    return os.path.isfile(settings.pmo_qcc_db_path)


def lookup_company_by_credit_code(db: Session, credit_code: str) -> dict | None:
    """
    按统一社会信用代码查询 qcc 企业信息。
    返回字段：id, name, credit_code, legal_person, status, founded_date,
              registered_capital, company_type, address, business_scope 等。
    """
    result = db.execute(
        text("""
            SELECT id, name, credit_code, legal_person, status,
                   founded_date, registered_capital, paid_capital,
                   company_type, business_term, taxpayer_qualification,
                   staff_size, insured_count, industry, region,
                   registration_authority, address, business_scope,
                   english_name, short_name, notes, tags, qcc_synced_at
            FROM qcc.companies
            WHERE credit_code = :credit_code
        """),
        {"credit_code": credit_code},
    ).fetchone()

    if not result:
        return None

    columns = [
        "id", "name", "credit_code", "legal_person", "status",
        "founded_date", "registered_capital", "paid_capital",
        "company_type", "business_term", "taxpayer_qualification",
        "staff_size", "insured_count", "industry", "region",
        "registration_authority", "address", "business_scope",
        "english_name", "short_name", "notes", "tags", "qcc_synced_at",
    ]
    return dict(zip(columns, result))


def lookup_company_by_name(db: Session, name: str) -> dict | None:
    """
    按企业名称模糊查询 qcc 企业信息（精确匹配优先）。
    """
    result = db.execute(
        text("""
            SELECT id, name, credit_code, legal_person, status,
                   founded_date, registered_capital, paid_capital,
                   company_type, business_term, taxpayer_qualification,
                   staff_size, insured_count, industry, region,
                   registration_authority, address, business_scope,
                   english_name, short_name, notes, tags, qcc_synced_at
            FROM qcc.companies
            WHERE name = :name
            LIMIT 1
        """),
        {"name": name},
    ).fetchone()

    if not result:
        return None

    columns = [
        "id", "name", "credit_code", "legal_person", "status",
        "founded_date", "registered_capital", "paid_capital",
        "company_type", "business_term", "taxpayer_qualification",
        "staff_size", "insured_count", "industry", "region",
        "registration_authority", "address", "business_scope",
        "english_name", "short_name", "notes", "tags", "qcc_synced_at",
    ]
    return dict(zip(columns, result))


def list_company_qualifications(
    db: Session, qcc_company_id: int
) -> list[dict]:
    """
    列出指定 qcc 企业的全部资质证照。
    返回每条：id, category, name, cert_no, level, status,
              valid_from, valid_to, issuer, issue_date, product_name,
              scope_name, cert_domain, cert_sequence, cert_industry,
              business_type, grade, extra_json。
    """
    rows = db.execute(
        text("""
            SELECT id, category, name, cert_no, level, status,
                   valid_from, valid_to, issuer, issue_date,
                   product_name, scope_name, cert_domain, cert_sequence,
                   cert_industry, business_type, grade, extra_json, source
            FROM qcc.qualifications
            WHERE company_id = :company_id
            ORDER BY
                CASE WHEN valid_to IS NULL THEN 1 ELSE 0 END,
                valid_to ASC,
                name ASC
        """),
        {"company_id": qcc_company_id},
    ).fetchall()

    columns = [
        "id", "category", "name", "cert_no", "level", "status",
        "valid_from", "valid_to", "issuer", "issue_date",
        "product_name", "scope_name", "cert_domain", "cert_sequence",
        "cert_industry", "business_type", "grade", "extra_json", "source",
    ]
    return [dict(zip(columns, row)) for row in rows]


def qualification_stats(db: Session, qcc_company_id: int) -> dict:
    """
    统计企业资质：总数、有效期内、即将到期（30天内）、已过期。
    """
    row = db.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE
                    WHEN (valid_to IS NULL OR date(valid_to) >= date('now'))
                    THEN 1 ELSE 0
                END) AS valid,
                SUM(CASE
                    WHEN valid_to IS NOT NULL
                    AND date(valid_to) >= date('now')
                    AND date(valid_to) <= date('now', '+30 days')
                    THEN 1 ELSE 0
                END) AS expiring_soon,
                SUM(CASE
                    WHEN valid_to IS NOT NULL
                    AND date(valid_to) < date('now')
                    THEN 1 ELSE 0
                END) AS expired
            FROM qcc.qualifications
            WHERE company_id = :company_id
        """),
        {"company_id": qcc_company_id},
    ).fetchone()

    if not row:
        return {"total": 0, "valid": 0, "expiring_soon": 0, "expired": 0}

    return {
        "total": row[0] or 0,
        "valid": row[1] or 0,
        "expiring_soon": row[2] or 0,
        "expired": row[3] or 0,
    }


def get_expiring_qualifications(
    db: Session, days: int = 30
) -> list[dict]:
    """
    列出即将到期（天数内）的资质，用于全局到期预警。
    """
    rows = db.execute(
        text("""
            SELECT
                q.id, q.company_id, q.category, q.name, q.cert_no,
                q.level, q.valid_from, q.valid_to, q.issuer, q.product_name,
                c.name AS company_name, c.credit_code
            FROM qcc.qualifications q
            JOIN qcc.companies c ON c.id = q.company_id
            WHERE q.valid_to IS NOT NULL
              AND date(q.valid_to) >= date('now')
              AND date(q.valid_to) <= date('now', :days_interval)
            ORDER BY q.valid_to ASC
        """),
        {"days_interval": f"+{days} days"},
    ).fetchall()

    columns = [
        "id", "company_id", "category", "name", "cert_no",
        "level", "valid_from", "valid_to", "issuer", "product_name",
        "company_name", "credit_code",
    ]
    return [dict(zip(columns, row)) for row in rows]
