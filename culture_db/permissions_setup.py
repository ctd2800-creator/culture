"""사용자 테이블 접근 권한 DDL 적용·시드·조회."""

from __future__ import annotations

from pathlib import Path

from culture_db.sql_util import ddl_without_grants
from culture_db.table_config import (
    INST1_TABLE_ORDER,
    TSHDEOA01_TABLE,
    USER_PERMISSION_TABLE_NAME,
)

_SQL_PATH = Path(__file__).resolve().parent / "user_permissions.sql"
_TABLE = f'public."{USER_PERMISSION_TABLE_NAME}"'

# 사용자별 접근 가능 테이블 권한 정의
#  - culture01: 모든 INST1 테이블 접근
#  - culture02: 그룹고객기본정보(TSHDEOA01) 만 접근
USER_TABLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "culture01": tuple(INST1_TABLE_ORDER),
    "culture02": (TSHDEOA01_TABLE,),
}


def ensure_user_permission_table(conn) -> None:
    ddl = ddl_without_grants(_SQL_PATH.read_text(encoding="utf-8"))
    with conn.cursor() as cur:
        cur.execute(ddl)


def seed_user_permissions(conn, *, force: bool = False) -> int:
    """권한 정의 upsert. force=False 이면 테이블이 비었을 때만 삽입."""
    with conn.cursor() as cur:
        if not force:
            cur.execute(f'SELECT COUNT(*) FROM {_TABLE}')
            if (cur.fetchone() or (0,))[0] > 0:
                return 0
        count = 0
        for member_id, tables in USER_TABLE_PERMISSIONS.items():
            # 정의된 사용자 권한을 깔끔하게 재설정
            cur.execute(f'DELETE FROM {_TABLE} WHERE "아이디" = %s', (member_id,))
            for table_code in tables:
                cur.execute(
                    f'INSERT INTO {_TABLE} ("아이디", "테이블코드") VALUES (%s, %s) '
                    f'ON CONFLICT ("아이디", "테이블코드") DO NOTHING',
                    (member_id, table_code),
                )
                count += 1
    return count


def setup_user_permissions(
    conn, *, seed: bool = True, force_seed: bool = False
) -> dict[str, int]:
    ensure_user_permission_table(conn)
    inserted = seed_user_permissions(conn, force=force_seed) if seed else 0
    with conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM {_TABLE}')
        total = (cur.fetchone() or (0,))[0]
    return {"inserted": inserted, "total": int(total)}


def fetch_allowed_tables(conn, member_id: str) -> set[str] | None:
    """사용자의 접근 가능 테이블 집합.

    권한 행이 하나도 없으면 None 을 반환(제한 없음 = 전체 접근)하여
    기존 사용자(culture03~10 등)의 동작을 유지한다.
    """
    member_id = (member_id or "").strip()
    if not member_id:
        return None
    with conn.cursor() as cur:
        cur.execute(
            f'SELECT "테이블코드" FROM {_TABLE} WHERE "아이디" = %s',
            (member_id,),
        )
        rows = cur.fetchall()
    if not rows:
        return None
    return {r[0] for r in rows if r and r[0]}
