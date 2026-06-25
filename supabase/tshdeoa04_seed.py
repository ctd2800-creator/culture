"""INST1.TSHDEOA04 초기 데이터 (202604 KFG)."""

from __future__ import annotations

from collections.abc import Iterator

from supabase.table_config import TSHDEOA04_SCHEMA, TSHDEOA04_TABLE
from supabase.tshdeoa01_seed import (
    TSHDEOA01_EAGER_MATERIALIZE_LIMIT,
    TSHDEOA01_LINKED_MONTH_COUNT,
    TSHDEOA01_ROWS_202604,
    TSHDEOA01_SAMPLE_ROWS,
    TSHDEOA01_SEED_MONTHS,
    SOURCE_MONTH,
    iter_rows_from_templates,
)

# 기준년월, 그룹회사코드, 그룹고객식별자, 직업분류, 급여이체여부, 급여이체금액,
# 최근3개월급여평균, 연소득, 근로소득, 사업소득, 총대출잔액, 연체잔액, 최대연체일수
TSHDEOA04_SAMPLE_ROWS: list[tuple] = [
    ("202604", "KFG", "1416493458", "1", "1", 4200000, 4100000, 52000000, 50000000, 2000000, 100000000, 0, 0),
    ("202604", "KFG", "1335048002", "2", "0", 0, 0, 38000000, 36000000, 2000000, 2270000, 0, 0),
    ("202604", "KFG", "1208562328", "3", "0", 0, 0, 45000000, 42000000, 3000000, 187474431, 0, 0),
    ("202604", "KFG", "1461756908", "1", "0", 0, 0, 32000000, 30000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1223547441", "2", "0", 0, 0, 28000000, 26000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1021177032", "1", "0", 0, 0, 55000000, 53000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1236450213", "1", "0", 0, 0, 42000000, 40000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1068461355", "2", "0", 0, 0, 36000000, 34000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1546708859", "1", "0", 0, 0, 29000000, 27000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1174388394", "1", "1", 3800000, 3750000, 48000000, 46000000, 2000000, 1300022, 0, 0),
    ("202604", "KFG", "1334961904", "2", "0", 0, 0, 31000000, 29000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1325679051", "1", "1", 3200000, 3100000, 41000000, 39000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1281075402", "3", "0", 0, 0, 27000000, 25000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1220047984", "1", "0", 0, 0, 33000000, 31000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1196057447", "1", "1", 4500000, 4400000, 62000000, 58000000, 4000000, 0, 0, 0),
    ("202604", "KFG", "1038131315", "2", "0", 0, 0, 24000000, 22000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1012986034", "1", "0", 0, 0, 35000000, 33000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1470375837", "1", "0", 0, 0, 30000000, 28000000, 2000000, 1425918, 0, 0),
    ("202604", "KFG", "1405511205", "1", "1", 5200000, 5100000, 72000000, 68000000, 4000000, 100000000, 0, 0),
    ("202604", "KFG", "1276558318", "2", "0", 0, 0, 26000000, 24000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1203411428", "3", "0", 0, 0, 22000000, 20000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1446565238", "1", "0", 0, 0, 40000000, 38000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1342475439", "2", "0", 0, 0, 37000000, 35000000, 2000000, 4708855, 0, 0),
    ("202604", "KFG", "1263284029", "1", "1", 3600000, 3550000, 49000000, 47000000, 2000000, 2864353, 0, 0),
    ("202604", "KFG", "1551559608", "2", "0", 0, 0, 25000000, 23000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1518729248", "1", "0", 0, 0, 28000000, 26000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1306390679", "3", "0", 0, 0, 23000000, 21000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1453518334", "2", "0", 0, 0, 21000000, 19000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1282906093", "1", "0", 0, 0, 20000000, 18000000, 2000000, 0, 0, 0),
    ("202604", "KFG", "1088697480", "2", "0", 0, 0, 32000000, 30000000, 2000000, 0, 120000, 15),
]

TSHDEOA04_ROWS = TSHDEOA04_SAMPLE_ROWS

SOURCE_MONTH = "202604"
TSHDEOA04_202604_TARGET_COUNT = TSHDEOA01_LINKED_MONTH_COUNT
TSHDEOA04_SEED_MONTHS = TSHDEOA01_SEED_MONTHS


def _vary_o04_attrs(attrs: list, i: int) -> list:
    out = list(attrs)
    off = i % 5
    out[0] = str((int(out[0] or "1") + off) % 4 or 1)
    if out[1] == "1":
        base = int(out[2] or 3000000)
        delta = (off * 50000 + i * 1000) % 200000
        out[2] = max(0, base + delta)
        out[3] = max(0, int(out[3] or out[2]) + delta // 2)
    for j in range(4, 7):
        base = int(out[j] or 30000000)
        out[j] = max(0, base + (off - 2) * 500000)
    for j in range(7, 9):
        base = int(out[j] or 0)
        out[j] = max(0, base + (off * 100000))
    out[9] = max(0, int(out[9] or 0) + (i % 3))
    return out


def _o04_attrs_for_customer(i: int, customer_id: str) -> list:
    template_by_cid = {str(row[2]).strip(): row for row in TSHDEOA04_SAMPLE_ROWS}
    if customer_id in template_by_cid:
        _, _, _, *attrs = template_by_cid[customer_id]
        return list(attrs)
    _, _, _, *attrs = TSHDEOA04_SAMPLE_ROWS[i % len(TSHDEOA04_SAMPLE_ROWS)]
    return _vary_o04_attrs(list(attrs), i)


def iter_o04_rows_202604(
    *,
    count: int = TSHDEOA04_202604_TARGET_COUNT,
) -> Iterator[tuple]:
    for i, o01_row in enumerate(
        iter_rows_from_templates(
            TSHDEOA01_SAMPLE_ROWS,
            month=SOURCE_MONTH,
            count=count,
        )
    ):
        _, grp, customer_id, *_ = o01_row
        customer_id = str(customer_id).strip()
        row_attrs = _o04_attrs_for_customer(i, customer_id)
        yield (SOURCE_MONTH, grp, customer_id, *row_attrs)


def iter_all_o04_seed_rows(
    *,
    count: int = TSHDEOA04_202604_TARGET_COUNT,
    months: tuple[str, ...] = TSHDEOA04_SEED_MONTHS,
) -> Iterator[tuple]:
    for row in iter_o04_rows_202604(count=count):
        tail = row[1:]
        for month in months:
            yield (month, *tail)


def expand_o04_rows_from_o01_customers(
    templates: list[tuple],
    o01_rows: list[tuple],
    *,
    month: str,
) -> list[tuple]:
    if len(o01_rows) != TSHDEOA04_202604_TARGET_COUNT:
        raise ValueError(
            f"TSHDEOA01 고객 수({len(o01_rows)})가 "
            f"목표({TSHDEOA04_202604_TARGET_COUNT})와 다릅니다."
        )

    template_by_cid = {str(row[2]).strip(): row for row in templates}
    used_ids: set[str] = set()
    rows: list[tuple] = []

    for i, o01_row in enumerate(o01_rows):
        _, grp, customer_id, *_ = o01_row
        customer_id = str(customer_id).strip()
        if customer_id in used_ids:
            raise ValueError(f"중복 고객식별자: {customer_id}")
        used_ids.add(customer_id)

        if customer_id in template_by_cid:
            _, _, _, *attrs = template_by_cid[customer_id]
            row_attrs = list(attrs)
        else:
            _, _, _, *attrs = templates[i % len(templates)]
            row_attrs = _vary_o04_attrs(list(attrs), i)

        rows.append((month, grp, customer_id, *row_attrs))

    return rows


def derive_rows_for_month(rows: list[tuple], month: str) -> list[tuple]:
    return [(month,) + row[1:] for row in rows]


if (
    TSHDEOA04_202604_TARGET_COUNT <= TSHDEOA01_EAGER_MATERIALIZE_LIMIT
    and TSHDEOA01_ROWS_202604
    and len(TSHDEOA01_ROWS_202604) == TSHDEOA04_202604_TARGET_COUNT
):
    TSHDEOA04_ROWS_202604 = expand_o04_rows_from_o01_customers(
        TSHDEOA04_SAMPLE_ROWS,
        TSHDEOA01_ROWS_202604,
        month=SOURCE_MONTH,
    )
    TSHDEOA04_ROWS_202603 = derive_rows_for_month(TSHDEOA04_ROWS_202604, "202603")
    TSHDEOA04_ROWS_202602 = derive_rows_for_month(TSHDEOA04_ROWS_202604, "202602")
    TSHDEOA04_ALL_ROWS: list[tuple] = (
        TSHDEOA04_ROWS_202604 + TSHDEOA04_ROWS_202603 + TSHDEOA04_ROWS_202602
    )
else:
    TSHDEOA04_ROWS_202604 = []
    TSHDEOA04_ROWS_202603 = []
    TSHDEOA04_ROWS_202602 = []
    TSHDEOA04_ALL_ROWS = []

TSHDEOA04_INSERT_SQL = f"""
INSERT INTO "{TSHDEOA04_SCHEMA}"."{TSHDEOA04_TABLE}" (
  "기준년월", "그룹회사코드", "그룹고객식별자",
  "그룹직업분류코드", "급여이체여부", "급여이체금액", "최근3개월급여이체평균금액",
  "연소득금액", "연본인근로소득", "연본인사업소득",
  "그룹총대출잔액", "그룹연체잔액", "그룹최대연체일수"
) VALUES (
  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
"""

TSHDEOA04_UPSERT_SQL = f"""
{TSHDEOA04_INSERT_SQL.rstrip()}
ON CONFLICT ("기준년월", "그룹회사코드", "그룹고객식별자") DO UPDATE SET
  "그룹직업분류코드" = EXCLUDED."그룹직업분류코드",
  "급여이체여부" = EXCLUDED."급여이체여부",
  "급여이체금액" = EXCLUDED."급여이체금액",
  "최근3개월급여이체평균금액" = EXCLUDED."최근3개월급여이체평균금액",
  "연소득금액" = EXCLUDED."연소득금액",
  "연본인근로소득" = EXCLUDED."연본인근로소득",
  "연본인사업소득" = EXCLUDED."연본인사업소득",
  "그룹총대출잔액" = EXCLUDED."그룹총대출잔액",
  "그룹연체잔액" = EXCLUDED."그룹연체잔액",
  "그룹최대연체일수" = EXCLUDED."그룹최대연체일수";
"""
