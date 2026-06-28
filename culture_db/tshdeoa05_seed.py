"""INST1.TSHDEOA05 초기 데이터 — TSHDEOA01 고객식별자 연동 (고객당 1계열사)."""

from __future__ import annotations

from collections.abc import Iterator

from culture_db.table_config import TSHDEOA05_SCHEMA, TSHDEOA05_TABLE
from culture_db.tshdeoa01_seed import (
    TSHDEOA01_SEED_MONTHS,
    iter_o01_customers_by_month,
)

# 원 그룹계열회사구분값 (3자리)
TSHDEOA05_AFFILIATE_CODES: tuple[str, ...] = (
    "001",  # 은행
    "002",  # 증권
    "003",  # 손보
    "004",  # 카드
    "005",  # 생명
    "006",  # 캐피탈
    "007",  # 저축은행
    "008",  # 기타
)

TSHDEOA05_SAMPLE_ROWS: list[tuple] = [
    ("202604", "001", "1416493458", "1", "20260115", "20270114"),
    ("202604", "004", "1335048002", "1", "20260201", "20270131"),
]

TSHDEOA05_ROWS = TSHDEOA05_SAMPLE_ROWS
TSHDEOA05_SEED_MONTHS = TSHDEOA01_SEED_MONTHS


def _o05_attrs_for_customer(i: int, customer_id: str) -> list:
    template_by_cid = {str(row[2]).strip(): row for row in TSHDEOA05_SAMPLE_ROWS}
    if customer_id in template_by_cid:
        _, aff, _, agree, start, end = template_by_cid[customer_id]
        return [aff, agree, start, end]
    aff = TSHDEOA05_AFFILIATE_CODES[i % len(TSHDEOA05_AFFILIATE_CODES)]
    day = (i % 28) + 1
    start = f"2026{(i % 3) + 1:02d}{day:02d}"
    end = f"2027{(i % 3) + 1:02d}{day:02d}"
    return [aff, "1", start, end]


def iter_all_o05_seed_rows(
    *,
    months: tuple[str, ...] = TSHDEOA05_SEED_MONTHS,
) -> Iterator[tuple]:
    for i, month, _, customer_id in iter_o01_customers_by_month(months):
        aff, agree, start, end = _o05_attrs_for_customer(i, customer_id)
        yield (month, aff, customer_id, agree, start, end)


TSHDEOA05_INSERT_SQL = f"""
INSERT INTO "{TSHDEOA05_SCHEMA}"."{TSHDEOA05_TABLE}" (
  "기준년월", "정보제공동의계열사구분내용", "그룹고객식별자",
  "계열사마케팅동의여부", "계열사마케팅동의년월일", "계열사마케팅동의종료예정년월일"
) VALUES (
  %s, %s, %s, %s, %s, %s
)
"""
