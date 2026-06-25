"""INST1.TSHDEOA02 초기 데이터 (202604 KFG)."""

from __future__ import annotations

from collections.abc import Iterator

from supabase.table_config import TSHDEOA02_SCHEMA, TSHDEOA02_TABLE
from supabase.tshdeoa01_seed import (
    TSHDEOA01_EAGER_MATERIALIZE_LIMIT,
    TSHDEOA01_LINKED_MONTH_COUNT,
    TSHDEOA01_ROWS_202604,
    TSHDEOA01_SAMPLE_ROWS,
    TSHDEOA01_SEED_MONTHS,
    SOURCE_MONTH,
    iter_rows_from_templates,
)

# 기준년월, 그룹회사코드, 그룹고객식별자, 최초거래, 최근거래, 거래기간, 창구, 비대면,
# 최고수신, 최고여신, 수신잔액, 여신잔액, 보유수신, 보유여신, 신규, 해지, 급여, 연금
TSHDEOA02_SAMPLE_ROWS: list[tuple] = [
    ("202604", "KFG", "1416493458", "19990308", "20260430", "18", 0, 4, 18219583, 100000000, 29428154, 100000000, 10, 1, 0, 0, "1", "0"),
    ("202604", "KFG", "1335048002", "20010119", "20260427", "18", 0, 0, 16858502, 2270000, 16861635, 2270000, 3, 1, 0, 0, "0", "0"),
    ("202604", "KFG", "1282906093", "20010209", "20251220", "17", 0, 0, 10, 0, 10, 0, 2, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1208562328", "20060418", "20260315", "16", 1, 0, 55796592, 187474431, 886938, 0, 4, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1461756908", "20150504", "20260430", "15", 0, 0, 3460000, 0, 5280000, 0, 2, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1223547441", "20080822", "20260428", "16", 0, 17, 4920000, 0, 5225952, 0, 3, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1021177032", "19930518", "20260108", "18", 0, 0, 5000000, 0, 1, 0, 1, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1236450213", "19950228", "20260331", "18", 0, 0, 913400, 0, 150214, 0, 4, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1068461355", "20030206", "20260415", "17", 0, 0, 400482, 0, 55788, 0, 1, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1546708859", "20230404", "20260425", "13", 0, 8, 3083755, 0, 3083755, 0, 1, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1174388394", "20000328", "20260309", "18", 0, 0, 1300022, 0, 1300022, 0, 2, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1334961904", "20040406", "20230617", "16", 0, 0, 4200000, 0, 0, 0, 2, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1325679051", "20211007", "20260424", "13", 0, 3, 875600, 0, 65800, 0, 2, 0, 1, 0, "1", "0"),
    ("202604", "KFG", "1281075402", "20010703", "20251230", "17", 0, 0, 8382623, 0, 35, 0, 1, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1220047984", "19921001", "20240705", "18", 0, 0, 5147058, 0, 3579, 0, 4, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1196057447", "20010129", "20260430", "18", 0, 0, 14074002, 0, 17973913, 0, 4, 0, 0, 0, "1", "1"),
    ("202604", "KFG", "1038131315", "20250312", "20260319", "13", 0, 0, 279, 0, 0, 0, 1, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1012986034", "19921001", "20260430", "18", 0, 30, 497000, 0, 157885, 0, 1, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1470375837", "20130521", "20260427", "15", 0, 0, 1425918, 0, 1425918, 0, 2, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1405511205", "19931123", "20260427", "18", 3, 0, 50005765, 100000000, 12229069, 0, 5, 0, 0, 0, "1", "1"),
    ("202604", "KFG", "1276558318", "19960326", "20251002", "18", 0, 0, 2423, 0, 2423, 0, 1, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1203411428", "19940523", "20241221", "18", 0, 0, 7332, 0, 7332, 0, 1, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1446565238", "20110209", "20260427", "15", 0, 2, 9414935, 0, 0, 0, 1, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1342475439", "19930917", "20260430", "18", 0, 0, 15982132, 0, 4708855, 0, 6, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1088697480", "19921001", "20260430", "18", 0, 0, 213372, 0, 60370, 0, 1, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1263284029", "20021030", "20260430", "17", 0, 19, 11964727, 0, 2864353, 0, 1, 0, 0, 0, "1", "0"),
    ("202604", "KFG", "1551559608", "20200114", "20260406", "03", 0, 0, 200000, 0, 200000, 0, 1, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1518729248", "20180228", "20230716", "14", 0, 0, 30957, 0, 14, 0, 2, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1306390679", "20090826", "20260421", "15", 0, 0, 1731223, 0, 0, 0, 1, 0, 0, 0, "0", "0"),
    ("202604", "KFG", "1453518334", "20111014", "20150620", "13", 0, 0, 474, 0, 474, 0, 2, 0, 0, 0, "0", "0"),
]

# 하위 호환
TSHDEOA02_ROWS = TSHDEOA02_SAMPLE_ROWS

SOURCE_MONTH = "202604"
TSHDEOA02_202604_TARGET_COUNT = TSHDEOA01_LINKED_MONTH_COUNT
TSHDEOA02_SEED_MONTHS = TSHDEOA01_SEED_MONTHS


def _vary_o02_attrs(attrs: list, i: int) -> list:
    """생성 고객용 거래 속성 소폭 변동."""
    out = list(attrs)
    off = i % 5
    out[3] = max(0, int(out[3]) + (i % 3))
    out[4] = max(0, int(out[4]) + (off % 2))
    for j in range(5, 9):
        base = int(out[j])
        delta = (off * 137 + i) % max(1, base // 50 + 1)
        out[j] = max(0, base - delta if i % 2 else base + delta)
    for j in range(9, 13):
        base = int(out[j])
        out[j] = max(0, min(10, base + ((i % 3) - 1)))
    return out


def _o02_attrs_for_customer(i: int, customer_id: str) -> list:
    template_by_cid = {str(row[2]).strip(): row for row in TSHDEOA02_SAMPLE_ROWS}
    if customer_id in template_by_cid:
        _, _, _, *attrs = template_by_cid[customer_id]
        return list(attrs)
    _, _, _, *attrs = TSHDEOA02_SAMPLE_ROWS[i % len(TSHDEOA02_SAMPLE_ROWS)]
    return _vary_o02_attrs(list(attrs), i)


def iter_o02_rows_202604(
    *,
    count: int = TSHDEOA02_202604_TARGET_COUNT,
) -> Iterator[tuple]:
    """TSHDEOA01 고객식별자 기준 TSHDEOA02 202604 행 스트리밍 생성."""
    for i, o01_row in enumerate(
        iter_rows_from_templates(
            TSHDEOA01_SAMPLE_ROWS,
            month=SOURCE_MONTH,
            count=count,
        )
    ):
        _, grp, customer_id, *_ = o01_row
        customer_id = str(customer_id).strip()
        row_attrs = _o02_attrs_for_customer(i, customer_id)
        yield (SOURCE_MONTH, grp, customer_id, *row_attrs)


def iter_all_o02_seed_rows(
    *,
    count: int = TSHDEOA02_202604_TARGET_COUNT,
    months: tuple[str, ...] = TSHDEOA02_SEED_MONTHS,
) -> Iterator[tuple]:
    for row in iter_o02_rows_202604(count=count):
        tail = row[1:]
        for month in months:
            yield (month, *tail)


def expand_o02_rows_from_o01_customers(
    templates: list[tuple],
    o01_rows: list[tuple],
    *,
    month: str,
) -> list[tuple]:
    """TSHDEOA02 샘플 속성 + TSHDEOA01 고객식별자로 count건 생성."""
    if len(o01_rows) != TSHDEOA02_202604_TARGET_COUNT:
        raise ValueError(
            f"TSHDEOA01 고객 수({len(o01_rows)})가 "
            f"목표({TSHDEOA02_202604_TARGET_COUNT})와 다릅니다."
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
            row_attrs = _vary_o02_attrs(list(attrs), i)

        rows.append((month, grp, customer_id, *row_attrs))

    return rows


def derive_rows_for_month(rows: list[tuple], month: str) -> list[tuple]:
    """기존 행을 참조해 동일 고객식별자·속성으로 다른 기준년월 데이터 생성."""
    return [(month,) + row[1:] for row in rows]


if (
    TSHDEOA02_202604_TARGET_COUNT <= TSHDEOA01_EAGER_MATERIALIZE_LIMIT
    and TSHDEOA01_ROWS_202604
    and len(TSHDEOA01_ROWS_202604) == TSHDEOA02_202604_TARGET_COUNT
):
    TSHDEOA02_ROWS_202604 = expand_o02_rows_from_o01_customers(
        TSHDEOA02_SAMPLE_ROWS,
        TSHDEOA01_ROWS_202604,
        month=SOURCE_MONTH,
    )
    TSHDEOA02_ROWS_202603 = derive_rows_for_month(TSHDEOA02_ROWS_202604, "202603")
    TSHDEOA02_ROWS_202602 = derive_rows_for_month(TSHDEOA02_ROWS_202604, "202602")
    TSHDEOA02_ALL_ROWS: list[tuple] = (
        TSHDEOA02_ROWS_202604 + TSHDEOA02_ROWS_202603 + TSHDEOA02_ROWS_202602
    )
else:
    TSHDEOA02_ROWS_202604 = []
    TSHDEOA02_ROWS_202603 = []
    TSHDEOA02_ROWS_202602 = []
    TSHDEOA02_ALL_ROWS = []

TSHDEOA02_INSERT_SQL = f"""
INSERT INTO "{TSHDEOA02_SCHEMA}"."{TSHDEOA02_TABLE}" (
  "기준년월", "그룹회사코드", "그룹고객식별자",
  "그룹최초거래년월일", "그룹최근거래년월일", "거래기간구분",
  "창구거래건수", "비대면거래건수",
  "최근5년최고수신잔액", "최근5년최고여신잔액", "수신잔액", "여신잔액",
  "보유수신상품계약수", "보유여신상품계약수",
  "당월상품신규계약수", "당월상품해지계약수",
  "급여이체여부", "연금이체여부"
) VALUES (
  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
"""

TSHDEOA02_UPSERT_SQL = f"""
{TSHDEOA02_INSERT_SQL.rstrip()}
ON CONFLICT ("기준년월", "그룹회사코드", "그룹고객식별자") DO UPDATE SET
  "그룹최초거래년월일" = EXCLUDED."그룹최초거래년월일",
  "그룹최근거래년월일" = EXCLUDED."그룹최근거래년월일",
  "거래기간구분" = EXCLUDED."거래기간구분",
  "창구거래건수" = EXCLUDED."창구거래건수",
  "비대면거래건수" = EXCLUDED."비대면거래건수",
  "최근5년최고수신잔액" = EXCLUDED."최근5년최고수신잔액",
  "최근5년최고여신잔액" = EXCLUDED."최근5년최고여신잔액",
  "수신잔액" = EXCLUDED."수신잔액",
  "여신잔액" = EXCLUDED."여신잔액",
  "보유수신상품계약수" = EXCLUDED."보유수신상품계약수",
  "보유여신상품계약수" = EXCLUDED."보유여신상품계약수",
  "당월상품신규계약수" = EXCLUDED."당월상품신규계약수",
  "당월상품해지계약수" = EXCLUDED."당월상품해지계약수",
  "급여이체여부" = EXCLUDED."급여이체여부",
  "연금이체여부" = EXCLUDED."연금이체여부";
"""
