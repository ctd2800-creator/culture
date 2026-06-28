"""INST1.TSHDEOA06 초기 데이터 — TSHDEOA01 고객식별자 연동."""

from __future__ import annotations

from collections.abc import Iterator

from culture_db.table_config import TSHDEOA06_SCHEMA, TSHDEOA06_TABLE
from culture_db.tshdeoa01_seed import (
    TSHDEOA01_SEED_MONTHS,
    iter_o01_customers_by_month,
)

_SEGMENTS: tuple[str, ...] = ("SEG1", "SEG2", "SEG3")

TSHDEOA06_SAMPLE_ROWS: list[tuple] = [
    ("202604", "KFG", "1416493458", "SEG1", 720, 680, 700, "03"),
    ("202604", "KFG", "1335048002", "SEG2", 650, 640, 645, "05"),
    ("202604", "KFG", "1208562328", "SEG3", 580, 600, 590, "07"),
]

TSHDEOA06_ROWS = TSHDEOA06_SAMPLE_ROWS
TSHDEOA06_SEED_MONTHS = TSHDEOA01_SEED_MONTHS


def _o06_attrs_for_customer(i: int, customer_id: str) -> list:
    template_by_cid = {str(row[2]).strip(): row for row in TSHDEOA06_SAMPLE_ROWS}
    if customer_id in template_by_cid:
        _, _, _, *attrs = template_by_cid[customer_id]
        return list(attrs)
    seg = _SEGMENTS[i % len(_SEGMENTS)]
    perf = 550 + (i % 250)
    gen = 520 + (i % 280)
    comb = (perf + gen) // 2
    grade = f"{1 + (comb % 10):02d}"
    return [seg, perf, gen, comb, grade]


def iter_all_o06_seed_rows(
    *,
    months: tuple[str, ...] = TSHDEOA06_SEED_MONTHS,
) -> Iterator[tuple]:
    for i, month, grp, customer_id in iter_o01_customers_by_month(months):
        yield (month, grp, customer_id, *_o06_attrs_for_customer(i, customer_id))


TSHDEOA06_INSERT_SQL = f"""
INSERT INTO "{TSHDEOA06_SCHEMA}"."{TSHDEOA06_TABLE}" (
  "기준년월", "그룹회사코드", "그룹고객식별자",
  "세그먼트분류명", "실적평점", "일반평점", "결합평점", "통합등급내용"
) VALUES (
  %s, %s, %s, %s, %s, %s, %s, %s
)
"""
