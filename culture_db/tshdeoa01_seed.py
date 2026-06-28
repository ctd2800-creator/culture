"""INST1.TSHDEOA01 초기 데이터 (202604 KFG)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from culture_db.table_config import TSHDEOA01_SCHEMA, TSHDEOA01_TABLE

# 기준년월, 그룹회사코드, 그룹고객식별자, 당월, 활동, 핵심, 성별, 연령, 본인등급, 최고등급, 개인사업자, 직장인, PB, 외국인
TSHDEOA01_SAMPLE_ROWS: list[tuple] = [
    ("202604", "KFG", "1446565238", 2, 2, 1, "1", "031", "9", "5", "0", "0", "0", "0"),
    ("202604", "KFG", "1236450213", 2, 1, 0, "1", "033", "9", "9", "0", "1", "0", "0"),
    ("202604", "KFG", "1342475439", 4, 2, 1, "2", "047", "5", "5", "0", "0", "0", "0"),
    ("202604", "KFG", "1038131315", 2, 1, 0, "1", "031", "5", "5", "0", "0", "0", "0"),
    ("202604", "KFG", "1220047984", 1, 0, 0, "1", "044", "9", "9", "0", "0", "0", "0"),
    ("202604", "KFG", "1021177032", 2, 0, 0, "1", "037", "9", "9", "0", "1", "0", "0"),
    ("202604", "KFG", "1405511205", 4, 2, 0, "2", "035", "9", "9", "0", "1", "0", "0"),
    ("202604", "KFG", "1208562328", 2, 0, 0, "1", "049", "9", "9", "1", "0", "0", "0"),
    ("202604", "KFG", "1334961904", 2, 1, 0, "2", "048", "9", "9", "0", "0", "0", "0"),
    ("202604", "KFG", "1196057447", 4, 4, 1, "2", "044", "5", "3", "0", "0", "0", "0"),
    ("202604", "KFG", "1416493458", 4, 4, 1, "1", "027", "3", "1", "0", "0", "0", "0"),
    ("202604", "KFG", "1281075402", 2, 0, 0, "1", "035", "9", "9", "0", "0", "0", "0"),
    ("202604", "KFG", "1461756908", 2, 2, 0, "1", "027", "9", "9", "0", "0", "0", "0"),
    ("202604", "KFG", "1470375837", 1, 1, 0, "1", "013", "9", "9", "0", "0", "0", "0"),
    ("202604", "KFG", "1282060693", 1, 0, 0, "2", "043", "9", "9", "0", "0", "0", "0"),
    ("202604", "KFG", "1174388394", 2, 1, 0, "1", "044", "9", "9", "0", "1", "0", "0"),
    ("202604", "KFG", "1325679051", 3, 3, 1, "2", "033", "5", "5", "0", "0", "0", "0"),
    ("202604", "KFG", "1551559608", 1, 1, 0, "2", "015", "9", "9", "0", "0", "0", "0"),
    ("202604", "KFG", "1276558318", 1, 0, 0, "1", "048", "9", "9", "0", "0", "0", "0"),
    ("202604", "KFG", "1518729248", 1, 0, 0, "1", "026", "9", "9", "0", "0", "0", "0"),
    ("202604", "KFG", "1306390679", 2, 0, 0, "2", "018", "9", "9", "0", "0", "0", "0"),
    ("202604", "KFG", "1012986034", 2, 2, 0, "2", "043", "9", "9", "0", "0", "0", "0"),
    ("202604", "KFG", "1223547441", 4, 2, 0, "2", "019", "9", "5", "0", "0", "0", "0"),
    ("202604", "KFG", "1068461355", 2, 2, 0, "1", "028", "9", "2", "0", "0", "0", "0"),
    ("202604", "KFG", "1453518334", 1, 0, 0, "2", "018", "9", "9", "0", "0", "0", "0"),
    ("202604", "KFG", "1203411428", 1, 0, 0, "2", "047", "9", "9", "0", "0", "0", "0"),
    ("202604", "KFG", "1546708859", 2, 1, 0, "1", "018", "9", "9", "0", "0", "0", "0"),
    ("202604", "KFG", "1335048002", 4, 2, 2, "2", "047", "9", "9", "0", "1", "0", "0"),
    ("202604", "KFG", "1263284029", 2, 2, 1, "1", "047", "5", "5", "0", "0", "0", "0"),
    ("202604", "KFG", "1253284029", 2, 2, 0, "2", "042", "9", "9", "0", "0", "0", "0"),
]

# 하위 호환
TSHDEOA01_ROWS = TSHDEOA01_SAMPLE_ROWS

SOURCE_MONTH = "202604"
TSHDEOA01_SEED_MONTHS: tuple[str, ...] = ("202602", "202603", "202604")
TSHDEOA01_MONTH_COUNTS: dict[str, int] = {
    "202602": 900_000,
    "202603": 950_000,
    "202604": 1_000_000,
}
TSHDEOA01_202604_TARGET_COUNT = TSHDEOA01_MONTH_COUNTS[SOURCE_MONTH]
# 연계 테이블 시드 상한 (최대 월 건수)
TSHDEOA01_LINKED_MONTH_COUNT = max(TSHDEOA01_MONTH_COUNTS.values())
# 메모리에 전건 적재 가능한 상한 (연계 테이블 시드용)
TSHDEOA01_EAGER_MATERIALIZE_LIMIT = 100_000
_GENERATED_ID_BASE = 3_000_000_000


def _vary_attrs(attrs: list[Any], i: int) -> list[Any]:
    out = list(attrs)
    off = i % 3
    out[0] = max(1, min(4, int(out[0]) + (off - 1)))
    out[1] = max(0, min(4, int(out[1]) + (off - 1)))
    out[2] = max(0, min(2, int(out[2]) + (1 if i % 7 == 0 else 0)))
    return out


def _customer_id_for_index(templates: list[tuple], i: int) -> str:
    template_len = len(templates)
    if i < template_len:
        return str(templates[i][2]).strip()
    return f"{_GENERATED_ID_BASE + (i - template_len):010d}"


def iter_rows_from_templates(
    templates: list[tuple],
    *,
    month: str,
    count: int,
) -> Iterator[tuple]:
    """샘플 행을 순환 참조해 count건 생성. 그룹고객식별자는 전건 유일."""
    if count < len(templates):
        raise ValueError(f"count({count})는 샘플 수({len(templates)}) 이상이어야 합니다.")

    template_len = len(templates)
    sample_ids = {str(t[2]).strip() for t in templates}
    if len(sample_ids) != template_len:
        raise ValueError("샘플 그룹고객식별자에 중복이 있습니다.")

    for i in range(count):
        _, grp, _, *template_attrs = templates[i % template_len]
        customer_id = _customer_id_for_index(templates, i)

        if i < template_len:
            row_attrs = list(template_attrs)
        else:
            row_attrs = _vary_attrs(list(template_attrs), i)

        yield (month, grp, customer_id, *row_attrs)


def expand_rows_from_templates(
    templates: list[tuple],
    *,
    month: str,
    count: int,
) -> list[tuple]:
    return list(iter_rows_from_templates(templates, month=month, count=count))


def derive_rows_for_month(rows: list[tuple], month: str) -> list[tuple]:
    """기존 행을 참조해 동일 고객식별자·속성으로 다른 기준년월 데이터 생성."""
    return [(month,) + row[1:] for row in rows]


def month_seed_count(month: str) -> int:
    if month not in TSHDEOA01_MONTH_COUNTS:
        raise KeyError(f"unknown seed month: {month}")
    return TSHDEOA01_MONTH_COUNTS[month]


def iter_o01_customers_by_month(
    months: tuple[str, ...] | None = None,
) -> Iterator[tuple[int, str, str, str]]:
    """(index, 기준년월, 그룹회사코드, 그룹고객식별자) per TSHDEOA01 고객."""
    for month in months or TSHDEOA01_SEED_MONTHS:
        count = month_seed_count(month)
        for i, o01_row in enumerate(
            iter_rows_from_templates(
                TSHDEOA01_SAMPLE_ROWS,
                month=month,
                count=count,
            )
        ):
            _, grp, customer_id, *_ = o01_row
            yield i, month, str(grp), str(customer_id).strip()


def iter_all_seed_rows(
    *,
    months: tuple[str, ...] = TSHDEOA01_SEED_MONTHS,
) -> Iterator[tuple]:
    """기준년월별 목표 건수에 맞춰 TSHDEOA01 행 스트리밍 생성."""
    for month in months:
        count = month_seed_count(month)
        yield from iter_rows_from_templates(
            TSHDEOA01_SAMPLE_ROWS,
            month=month,
            count=count,
        )


def _materialize_if_small() -> tuple[list[tuple], list[tuple], list[tuple], list[tuple]]:
    count = TSHDEOA01_202604_TARGET_COUNT
    if count > TSHDEOA01_EAGER_MATERIALIZE_LIMIT:
        return [], [], [], []
    rows_202604 = expand_rows_from_templates(
        TSHDEOA01_SAMPLE_ROWS,
        month=SOURCE_MONTH,
        count=count,
    )
    rows_202603 = derive_rows_for_month(rows_202604, "202603")
    rows_202602 = derive_rows_for_month(rows_202604, "202602")
    all_rows = rows_202604 + rows_202603 + rows_202602
    return rows_202604, rows_202603, rows_202602, all_rows


TSHDEOA01_ROWS_202604, TSHDEOA01_ROWS_202603, TSHDEOA01_ROWS_202602, TSHDEOA01_ALL_ROWS = (
    _materialize_if_small()
)

TSHDEOA01_INSERT_SQL = f"""
INSERT INTO "{TSHDEOA01_SCHEMA}"."{TSHDEOA01_TABLE}" (
  "기준년월", "그룹회사코드", "그룹고객식별자",
  "당월고객계열사수", "활동고객계열사수", "핵심고객계열사수",
  "성별구분", "연령코드",
  "KB스타클럽그룹본인등급", "KB스타클럽그룹최고등급",
  "개인사업자여부", "직장인여부", "PB고객여부", "외국인여부"
) VALUES (
  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
"""

TSHDEOA01_UPSERT_SQL = f"""
{TSHDEOA01_INSERT_SQL.rstrip()}
ON CONFLICT ("기준년월", "그룹회사코드", "그룹고객식별자") DO UPDATE SET
  "당월고객계열사수" = EXCLUDED."당월고객계열사수",
  "활동고객계열사수" = EXCLUDED."활동고객계열사수",
  "핵심고객계열사수" = EXCLUDED."핵심고객계열사수",
  "성별구분" = EXCLUDED."성별구분",
  "연령코드" = EXCLUDED."연령코드",
  "KB스타클럽그룹본인등급" = EXCLUDED."KB스타클럽그룹본인등급",
  "KB스타클럽그룹최고등급" = EXCLUDED."KB스타클럽그룹최고등급",
  "개인사업자여부" = EXCLUDED."개인사업자여부",
  "직장인여부" = EXCLUDED."직장인여부",
  "PB고객여부" = EXCLUDED."PB고객여부",
  "외국인여부" = EXCLUDED."외국인여부";
"""
