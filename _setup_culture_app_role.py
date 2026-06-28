"""앱 전용 DB 계정(culture_app) 생성 및 Culture 전용 객체 소유권 이전.

- 마스터(postgres) 비밀번호가 바뀌어도 앱은 영향받지 않도록 분리.
- Culture 전용 객체(INST1 스키마, public.회원)만
  culture_app 소유로 이전. 다른 앱의 public 테이블은 건드리지 않음.

실행: postgres(마스터)로 접속된 상태에서 1회 실행.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv(".env.local")

from culture_db.culture_db import connect_culture_db

APP_ROLE = "culture_app"
APP_PASSWORD = os.environ.get("CULTURE_APP_DB_PASSWORD", "Culture_App_2026_KbFinPm")

INST1_TABLES = [
    "TSHDEOA01",
    "TSHDEOA02",
    "TSHDEOA03",
    "TSHDEOA04",
    "TSHDEOA05",
    "TSHDEOA06",
    "TSHDE0ZCD",
]
PUBLIC_TABLES = ["회원"]


def main() -> None:
    conn = connect_culture_db()
    conn.autocommit = True
    cur = conn.cursor()

    # 1) 역할 생성 (없을 때만)
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,))
    if cur.fetchone():
        cur.execute(
            f'ALTER ROLE "{APP_ROLE}" WITH LOGIN INHERIT PASSWORD %s',
            (APP_PASSWORD,),
        )
        print(f"역할 {APP_ROLE} 이미 존재 → 비밀번호/속성 갱신")
    else:
        cur.execute(
            f'CREATE ROLE "{APP_ROLE}" WITH LOGIN INHERIT PASSWORD %s',
            (APP_PASSWORD,),
        )
        print(f"역할 {APP_ROLE} 생성")

    # 2) 소유권 이전을 위해 master를 culture_app 멤버로 추가
    cur.execute(f'GRANT "{APP_ROLE}" TO CURRENT_USER')

    # 3) DB 접속 권한
    cur.execute(f'GRANT CONNECT ON DATABASE pm_agent TO "{APP_ROLE}"')

    # 4) INST1 스키마 + 테이블 소유권 이전 (Culture 전용)
    cur.execute(f'ALTER SCHEMA "INST1" OWNER TO "{APP_ROLE}"')
    for t in INST1_TABLES:
        cur.execute(f'ALTER TABLE "INST1"."{t}" OWNER TO "{APP_ROLE}"')
    print(f"INST1 스키마 + {len(INST1_TABLES)}개 테이블 소유권 이전")

    # 5) public 스키마 사용/생성 권한 (다른 앱 객체는 그대로 둠)
    cur.execute(f'GRANT USAGE, CREATE ON SCHEMA public TO "{APP_ROLE}"')

    # 6) Culture 전용 public 테이블만 소유권 이전
    for t in PUBLIC_TABLES:
        cur.execute(f'ALTER TABLE public."{t}" OWNER TO "{APP_ROLE}"')
    print(f"public Culture 테이블 {len(PUBLIC_TABLES)}개 소유권 이전")

    # 7) 검증
    cur.execute(
        "SELECT schemaname, tablename, tableowner FROM pg_tables "
        "WHERE tableowner = %s ORDER BY 1,2",
        (APP_ROLE,),
    )
    print("--- culture_app 소유 테이블 ---")
    for r in cur.fetchall():
        print(r)

    conn.close()
    print("완료")


if __name__ == "__main__":
    main()
