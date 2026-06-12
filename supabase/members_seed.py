"""회원 테이블 초기 데이터 10명."""

from __future__ import annotations

from supabase.table_config import MEMBER_TABLE_NAME

# (아이디, 평문비밀번호, 회원명, 이메일, 부서명)
MEMBER_ROWS: list[tuple[str, str, str, str, str]] = [
    ("culture01", "Pass01!culture", "김민수", "culture01@example.com", "디지털혁신팀"),
    ("culture02", "Pass02!culture", "이서연", "culture02@example.com", "데이터분석팀"),
    ("culture03", "Pass03!culture", "박지훈", "culture03@example.com", "리스크관리팀"),
    ("culture04", "Pass04!culture", "최유진", "culture04@example.com", "고객경험팀"),
    ("culture05", "Pass05!culture", "정하은", "culture05@example.com", "IT기획팀"),
    ("culture06", "Pass06!culture", "강도윤", "culture06@example.com", "준법감시팀"),
    ("culture07", "Pass07!culture", "윤서아", "culture07@example.com", "마케팅팀"),
    ("culture08", "Pass08!culture", "임준호", "culture08@example.com", "재무전략팀"),
    ("culture09", "Pass09!culture", "한소희", "culture09@example.com", "AI혁신센터"),
    ("culture10", "Pass10!culture", "오태민", "culture10@example.com", "경영지원팀"),
]

MEMBER_UPSERT_SQL = f"""
INSERT INTO public."{MEMBER_TABLE_NAME}" (
  "아이디", "비밀번호", "회원명", "이메일", "부서명", "활성여부"
) VALUES (%s, %s, %s, %s, %s, true)
ON CONFLICT ("아이디") DO UPDATE SET
  "비밀번호" = EXCLUDED."비밀번호",
  "회원명" = EXCLUDED."회원명",
  "이메일" = EXCLUDED."이메일",
  "부서명" = EXCLUDED."부서명",
  "활성여부" = EXCLUDED."활성여부";
"""
