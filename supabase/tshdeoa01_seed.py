"""INST1.TSHDEOA01 초기 데이터 (202604 KFG)."""

from __future__ import annotations

from supabase.table_config import TSHDEOA01_SCHEMA, TSHDEOA01_TABLE

# 기준년월, 그룹회사코드, 그룹고객식별자, 당월, 활동, 핵심, 성별, 연령, 본인등급, 최고등급, 개인사업자, 직장인, PB, 외국인
TSHDEOA01_SAMPLE_ROWS: list[tuple] = [    ("202604", "KFG", "1446565238", 2, 2, 1, "1", "031", "9", "5", "0", "0", "0", "0"),
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
TSHDEOA01_202604_TARGET_COUNT = 970


def expand_rows_from_templates(
    templates: list[tuple],
    *,
    month: str,
    count: int,
) -> list[tuple]:
    """샘플 행을 순환 참조해 count건 생성. 그룹고객식별자는 전건 유일."""
    if count < len(templates):
        raise ValueError(f"count({count})는 샘플 수({len(templates)}) 이상이어야 합니다.")

    used_ids: set[str] = set()
    rows: list[tuple] = []

    for i in range(count):
        yyyymm, grp, template_cid, *attrs = templates[i % len(templates)]
        if i < len(templates):
            customer_id = str(template_cid).strip()
            row_attrs = list(attrs)
        else:
            seq = 970_000_0000 + i
            customer_id = str(seq)
            while customer_id in used_ids:
                seq += 1
                customer_id = str(seq)
            row_attrs = list(attrs)
            off = i % 3
            row_attrs[0] = max(1, min(4, int(row_attrs[0]) + (off - 1)))
            row_attrs[1] = max(0, min(4, int(row_attrs[1]) + (off - 1)))
            row_attrs[2] = max(0, min(2, int(row_attrs[2]) + (1 if i % 7 == 0 else 0)))

        if customer_id in used_ids:
            raise ValueError(f"중복 고객식별자: {customer_id}")
        used_ids.add(customer_id)
        rows.append((month, grp, customer_id, *row_attrs))

    return rows


def derive_rows_for_month(rows: list[tuple], month: str) -> list[tuple]:
    """기존 행을 참조해 동일 고객식별자·속성으로 다른 기준년월 데이터 생성."""
    return [(month,) + row[1:] for row in rows]


TSHDEOA01_ROWS_202604 = expand_rows_from_templates(
    TSHDEOA01_SAMPLE_ROWS,
    month=SOURCE_MONTH,
    count=TSHDEOA01_202604_TARGET_COUNT,
)
TSHDEOA01_ROWS_202603 = derive_rows_for_month(TSHDEOA01_ROWS_202604, "202603")
TSHDEOA01_ROWS_202602 = derive_rows_for_month(TSHDEOA01_ROWS_202604, "202602")
TSHDEOA01_ALL_ROWS: list[tuple] = (
    TSHDEOA01_ROWS_202604 + TSHDEOA01_ROWS_202603 + TSHDEOA01_ROWS_202602
)

TSHDEOA01_UPSERT_SQL = f"""
INSERT INTO "{TSHDEOA01_SCHEMA}"."{TSHDEOA01_TABLE}" (
  "기준년월", "그룹회사코드", "그룹고객식별자",
  "당월고객계열사수", "활동고객계열사수", "핵심고객계열사수",
  "성별구분", "연령코드",
  "KB스타클럽그룹본인등급", "KB스타클럽그룹최고등급",
  "개인사업자여부", "직장인여부", "PB고객여부", "외국인여부"
) VALUES (
  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
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
