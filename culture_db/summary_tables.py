"""월별 사전집계(요약) 테이블 — 대용량 COUNT 집계 가속.

원본 테이블(월 ~1,000만 행)을 매번 GROUP BY 하는 대신, 자주 쓰는 차원
조합의 고객수를 미리 계산해 둔 작은 요약 테이블에서 조회한다.

핵심 아이디어: COUNT 는 가산적이므로 **요약 테이블의 차원이 요청 차원의
상위집합이면**, 요약 테이블을 다시 GROUP BY 하고 SUM("고객수") 하면 임의의
하위 조합 질문에 정확히 답할 수 있다. 따라서 차원을 적당히 넓게 잡은 요약
테이블 몇 개로 여러 추천 질문을 모두 커버한다.

요약 테이블에 없는 차원/측정값(SUM 등)·고객 단건 조회는 매칭되지 않으며,
이 경우 호출부는 기존 원본 쿼리로 폴백한다(정확하지만 느림).

요약 테이블 스키마: (기준년월, 그룹회사코드, <차원들...>, 고객수)
- 모든 요약은 그룹고객식별자 기준 1:1(고객당 1행) 테이블에서 만든다.
- TSHDEOA02 는 TSHDEOA01 과 동일 고객(1:1 조인)이라 조인 요약도 fan-out 없음.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from culture_db.table_config import (
    INST1_JOIN_KEYS,
    INST1_TABLE_SQL_ALIAS,
    TSHDEOA01_SCHEMA,
    inst1_join_keys_between,
    inst1_table_has_group_company,
)

_SCHEMA = TSHDEOA01_SCHEMA

# 요약 테이블명 접두사 — 데이터 사전(스키마 검색) 인덱싱/검색에서 제외하는 데 사용.
SUMMARY_TABLE_PREFIX = "요약"


def is_summary_table(table: str) -> bool:
    """내부 가속용 사전집계(요약) 테이블 여부."""
    return (table or "").startswith(SUMMARY_TABLE_PREFIX)


@dataclass(frozen=True)
class SummarySpec:
    """월별 사전집계 요약 테이블 한 개의 정의.

    - name: 요약 테이블명(INST1 스키마)
    - source_tables: 원본 논리 테이블(조인 순서). 단일 집계면 길이 1.
    - dim_pairs: 차원 (테이블, 컬럼) 튜플. 단일 집계도 (테이블, 컬럼)로 표기.
    """

    name: str
    source_tables: tuple[str, ...]
    dim_pairs: tuple[tuple[str, str], ...]

    @property
    def dim_columns(self) -> tuple[str, ...]:
        return tuple(col for _, col in self.dim_pairs)

    @property
    def is_join(self) -> bool:
        return len(self.source_tables) > 1

    @property
    def primary_table(self) -> str:
        return self.source_tables[0]

    @property
    def has_group_company(self) -> bool:
        return inst1_table_has_group_company(self.primary_table)


# 추천 질문 커버리지:
#  - "스타클럽등급별, 성별구분별 고객수"  → 고객속성 요약 (최고등급 × 성별)
#  - "최근 3개월간 스타클럽등급 변동"      → 고객속성 요약 (최고등급, 기준년월 축)
#  - "연령코드별, 거래기간구분별 고객수"   → 01·02 조인 요약 (연령 × 거래기간)
SUMMARY_SPECS: tuple[SummarySpec, ...] = (
    SummarySpec(
        name="요약_TSHDEOA01_고객속성월별",
        source_tables=("TSHDEOA01",),
        dim_pairs=(
            ("TSHDEOA01", "성별구분"),
            ("TSHDEOA01", "연령코드"),
            ("TSHDEOA01", "KB스타클럽그룹본인등급"),
            ("TSHDEOA01", "KB스타클럽그룹최고등급"),
        ),
    ),
    SummarySpec(
        name="요약_TSHDEOA01_TSHDEOA02_연령거래기간월별",
        source_tables=("TSHDEOA01", "TSHDEOA02"),
        dim_pairs=(
            ("TSHDEOA01", "연령코드"),
            ("TSHDEOA02", "거래기간구분"),
        ),
    ),
)


# ---------------------------------------------------------------------------
# 매칭 (요청 → 요약 스펙)
# ---------------------------------------------------------------------------
def find_single_summary(logical_table: str, requested_dims) -> SummarySpec | None:
    """단일 테이블 COUNT 집계를 커버하는 요약 스펙(차원 ⊇ 요청)."""
    want = set(requested_dims)
    for spec in SUMMARY_SPECS:
        if spec.is_join:
            continue
        if spec.primary_table != logical_table:
            continue
        if want <= set(spec.dim_columns):
            return spec
    return None


def find_join_summary(join_tables, requested_pairs) -> SummarySpec | None:
    """조인 COUNT 집계를 커버하는 요약 스펙(원본 동일 + 차원쌍 ⊇ 요청)."""
    jt = set(join_tables)
    want = set(requested_pairs)
    for spec in SUMMARY_SPECS:
        if not spec.is_join:
            continue
        if set(spec.source_tables) != jt:
            continue
        if want <= set(spec.dim_pairs):
            return spec
    return None


# ---------------------------------------------------------------------------
# 조회 쿼리 빌더 (요약 테이블 대상)
# ---------------------------------------------------------------------------
def build_summary_query(
    spec: SummarySpec,
    *,
    group_by_cols: list[str],
    group_company: str,
    month: str,
    recent_months: int = 0,
) -> tuple[str, list, str]:
    """요약 테이블 조회용 (exec_sql, params, display_sql) 생성.

    group_by_cols 에는 '기준년월'이 포함될 수 있다(최근N개월 추이 등).
    """
    fqn = f'"{_SCHEMA}"."{spec.name}"'
    has_grp = spec.has_group_company
    sel = ", ".join(f'"{c}"' for c in group_by_cols)
    month_in_gb = "기준년월" in group_by_cols
    rn = int(recent_months or 0)

    where_exec: list[str] = []
    where_disp: list[str] = []
    params: list = []

    if rn > 0:
        if has_grp:
            where_exec.append(
                f'"기준년월" IN (SELECT DISTINCT "기준년월" FROM {fqn} '
                f'WHERE "그룹회사코드" = %s ORDER BY "기준년월" DESC LIMIT {rn})'
            )
            params.append(group_company)
            where_disp.append(
                f'"기준년월" IN (SELECT DISTINCT "기준년월" FROM {fqn} '
                f"WHERE \"그룹회사코드\" = '{group_company}' "
                f'ORDER BY "기준년월" DESC LIMIT {rn})'
            )
        else:
            where_exec.append(
                f'"기준년월" IN (SELECT DISTINCT "기준년월" FROM {fqn} '
                f'ORDER BY "기준년월" DESC LIMIT {rn})'
            )
            where_disp.append(where_exec[-1])
    elif month and not month_in_gb:
        where_exec.append('"기준년월" = %s')
        params.append(month)
        where_disp.append(f'"기준년월" = \'{month}\'')

    if has_grp:
        where_exec.append('"그룹회사코드" = %s')
        params.append(group_company)
        where_disp.append(f'"그룹회사코드" = \'{group_company}\'')

    where_e = f"WHERE {' AND '.join(where_exec)} " if where_exec else ""
    where_d = f"WHERE {' AND '.join(where_disp)}\n" if where_disp else ""

    exec_sql = (
        f'SELECT {sel}, SUM("고객수") AS "고객수" '
        f"FROM {fqn} {where_e}"
        f"GROUP BY {sel} ORDER BY {sel}"
    )
    display_sql = (
        f"SELECT {sel},\n       SUM(\"고객수\") AS \"고객수\"\n"
        f"FROM {fqn}\n{where_d}"
        f"GROUP BY {sel}\nORDER BY {sel};"
    )
    return exec_sql, params, display_sql


# ---------------------------------------------------------------------------
# 요약 테이블 생성/갱신
# ---------------------------------------------------------------------------
def _create_ddl(spec: SummarySpec) -> str:
    cols = ['"기준년월" varchar NOT NULL']
    if spec.has_group_company:
        cols.append('"그룹회사코드" varchar NOT NULL')
    for _, col in spec.dim_pairs:
        cols.append(f'"{col}" varchar')
    cols.append('"고객수" bigint NOT NULL')
    return f'CREATE TABLE IF NOT EXISTS "{_SCHEMA}"."{spec.name}" (\n  ' + ",\n  ".join(cols) + "\n)"


def _insert_select_sql(spec: SummarySpec) -> str:
    """원본에서 GROUP BY 하여 요약 테이블을 채우는 INSERT ... SELECT."""
    primary = spec.primary_table
    palias = INST1_TABLE_SQL_ALIAS[primary]
    has_grp = spec.has_group_company

    insert_cols = ['"기준년월"']
    if has_grp:
        insert_cols.append('"그룹회사코드"')
    insert_cols += [f'"{col}"' for _, col in spec.dim_pairs]
    insert_cols.append('"고객수"')

    sel = [f'{palias}."기준년월"']
    if has_grp:
        sel.append(f'{palias}."그룹회사코드"')
    sel += [f'{INST1_TABLE_SQL_ALIAS[t]}."{c}"' for t, c in spec.dim_pairs]
    sel.append(f'COUNT({palias}."그룹고객식별자")')

    from_sql = f'"{_SCHEMA}"."{primary}" {palias}'
    for t in spec.source_tables[1:]:
        alias = INST1_TABLE_SQL_ALIAS[t]
        on_parts = [
            f'{palias}."{k}" = {alias}."{k}"'
            for k in inst1_join_keys_between(primary, t)
        ]
        from_sql += (
            f'\n  INNER JOIN "{_SCHEMA}"."{t}" {alias} ON ' + " AND ".join(on_parts)
        )

    grp = [f'{palias}."기준년월"']
    if has_grp:
        grp.append(f'{palias}."그룹회사코드"')
    grp += [f'{INST1_TABLE_SQL_ALIAS[t]}."{c}"' for t, c in spec.dim_pairs]

    return (
        f'INSERT INTO "{_SCHEMA}"."{spec.name}" ({", ".join(insert_cols)})\n'
        f'SELECT {", ".join(sel)}\n'
        f"FROM {from_sql}\n"
        f'GROUP BY {", ".join(grp)}'
    )


def build_summary_tables(conn, *, analyze: bool = True) -> list[str]:
    """등록된 모든 요약 테이블을 생성(IF NOT EXISTS)·재적재(TRUNCATE+INSERT).

    멱등하며, 끝에 commit 한다. 생성/갱신한 요약 테이블명을 반환한다.
    """
    built: list[str] = []
    with conn.cursor() as cur:
        for spec in SUMMARY_SPECS:
            started = time.time()
            cur.execute(_create_ddl(spec))
            cur.execute(f'TRUNCATE "{_SCHEMA}"."{spec.name}"')
            cur.execute(_insert_select_sql(spec))
            cur.execute(
                f'CREATE INDEX IF NOT EXISTS "{spec.name}_grp_month" '
                f'ON "{_SCHEMA}"."{spec.name}" ("그룹회사코드", "기준년월")'
                if spec.has_group_company
                else f'CREATE INDEX IF NOT EXISTS "{spec.name}_month" '
                f'ON "{_SCHEMA}"."{spec.name}" ("기준년월")'
            )
            if analyze:
                cur.execute(f'ANALYZE "{_SCHEMA}"."{spec.name}"')
            cur.execute(f'SELECT COUNT(*) FROM "{_SCHEMA}"."{spec.name}"')
            n = cur.fetchone()[0]
            print(
                f"  [summary] {spec.name}: {n:,} rows ({time.time() - started:.0f}s)",
                flush=True,
            )
            built.append(spec.name)
    conn.commit()
    return built


def main() -> None:
    import psycopg2

    from culture_db.culture_db import aurora_db_url

    print("월별 사전집계(요약) 테이블 생성 시작", flush=True)
    started = time.time()
    with psycopg2.connect(aurora_db_url()) as conn:
        build_summary_tables(conn)
    print(f"OK: 요약 테이블 생성 완료 ({time.time() - started:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
