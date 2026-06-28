"""회원 로그인 검증."""

from __future__ import annotations

from typing import Any

from werkzeug.security import check_password_hash

from culture_db.table_config import MEMBER_TABLE_NAME


def authenticate_member(conn, member_id: str, password: str) -> dict[str, Any] | None:
    """아이디·비밀번호 검증. 성공 시 세션에 넣을 회원 정보(비밀번호 제외)."""
    member_id = (member_id or "").strip()
    password = password or ""
    if not member_id or not password:
        return None

    with conn.cursor() as cur:
        cur.execute(
            f'''
            SELECT "아이디", "비밀번호", "회원명", "이메일", "부서명", "활성여부"
            FROM public."{MEMBER_TABLE_NAME}"
            WHERE "아이디" = %s
            ''',
            (member_id,),
        )
        row = cur.fetchone()

    if not row:
        return None
    user_id, pw_hash, name, email, dept, active = row
    if not active:
        return None
    if not check_password_hash(pw_hash, password):
        return None

    return {
        "아이디": user_id,
        "회원명": name,
        "이메일": email or "",
        "부서명": dept or "",
    }
