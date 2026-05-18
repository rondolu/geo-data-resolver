"""Geocoding SQL 契約測試。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read_sql(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_contract_coordinate_query_uses_active_and_original_precision():
    """驗證 contract coordinate query 使用 ACTIVE 篩選且不使用四位小數 round。"""
    sql = _read_sql("sql/geocoding_query_contract_coordinates.sql")
    assert "WHERE status = 'ACTIVE'" in sql
    assert "ROUND(SAFE_CAST(longitude AS FLOAT64), 4)" not in sql
    assert "ROUND(SAFE_CAST(latitude AS FLOAT64), 4)" not in sql


def test_address_queries_use_current_application_join():
    """驗證 address query SQL 使用 current_application_id join 條件。"""
    contact_sql = _read_sql("sql/geocoding_query_contact_address.sql")
    residence_sql = _read_sql("sql/geocoding_query_residence_address.sql")

    assert "appl.id = cust.current_application_id" in contact_sql
    assert "appl.id = cust.current_application_id" in residence_sql


def test_address_updates_use_current_date_and_current_application_join():
    """驗證 address update SQL 使用 CURRENT_DATE() 與 current_application_id join。"""
    contact_update = _read_sql("sql/geocoding_update_contact_address.sql")
    residence_update = _read_sql("sql/geocoding_update_residence_address.sql")

    assert "CURRENT_DATE()" in contact_update
    assert "CURRENT_DATE()" in residence_update
    assert "appl.id = cust.current_application_id" in contact_update
    assert "appl.id = cust.current_application_id" in residence_update


def test_contract_update_sql_is_disabled_by_comment():
    """驗證 contract update SQL 全檔以 block comment 停用。"""
    sql = _read_sql("sql/geocoding_update_contract_coordinates.sql").strip()
    if sql.startswith("/*"):
        assert sql.endswith("*/")
    else:
        non_empty_lines = [line for line in sql.splitlines() if line.strip()]
        assert non_empty_lines
        assert all(line.lstrip().startswith("--") for line in non_empty_lines)
