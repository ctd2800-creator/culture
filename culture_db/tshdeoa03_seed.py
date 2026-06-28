"""INST1.TSHDEOA03 초기 데이터 — TSHDEOA01 고객식별자 연동."""

from __future__ import annotations

from collections.abc import Iterator

from culture_db.table_config import TSHDEOA03_SCHEMA, TSHDEOA03_TABLE
from culture_db.tshdeoa01_seed import (
    TSHDEOA01_SEED_MONTHS,
    iter_o01_customers_by_month,
)

_AFFILIATE_YNS = 7

TSHDEOA03_SAMPLE_ROWS: list[tuple] = [
    (
        "202604", "KFG", "1416493458",
        "062", "135", "1", "1", "0", "1", "1",
        3, "1", "1", "0", "1", "0", "0", "0",
        2, "1", "0", "0", "1", "0", "0", "0",
    ),
    (
        "202604", "KFG", "1335048002",
        "045", "087", "0", "1", "1", "0", "0",
        1, "1", "0", "0", "0", "0", "0", "0",
        1, "1", "0", "0", "0", "0", "0", "0",
    ),
]

TSHDEOA03_ROWS = TSHDEOA03_SAMPLE_ROWS
TSHDEOA03_SEED_MONTHS = TSHDEOA01_SEED_MONTHS


def _yn(flag: bool) -> str:
    return "1" if flag else "0"


def _o03_attrs_for_customer(i: int, customer_id: str) -> list:
    template_by_cid = {str(row[2]).strip(): row for row in TSHDEOA03_SAMPLE_ROWS}
    if customer_id in template_by_cid:
        _, _, _, *attrs = template_by_cid[customer_id]
        return list(attrs)
    off = i % 997
    work_zip = f"{(off + 11) % 999 + 1:03d}"
    home_zip = f"{(off * 3 + 7) % 999 + 1:03d}"
    flags = [_yn((i >> j) & 1) for j in range(5)]
    mkt_flags = [_yn((i + j) % 3 == 0) for j in range(_AFFILIATE_YNS)]
    mkt_count = sum(int(x) for x in mkt_flags)
    grp_flags = [_yn((i + j) % 4 == 0) for j in range(_AFFILIATE_YNS)]
    grp_count = sum(int(x) for x in grp_flags)
    return [
        work_zip,
        home_zip,
        *flags,
        mkt_count,
        *mkt_flags,
        grp_count,
        *grp_flags,
    ]


def iter_all_o03_seed_rows(
    *,
    months: tuple[str, ...] = TSHDEOA03_SEED_MONTHS,
) -> Iterator[tuple]:
    for i, month, grp, customer_id in iter_o01_customers_by_month(months):
        yield (month, grp, customer_id, *_o03_attrs_for_customer(i, customer_id))


TSHDEOA03_INSERT_SQL = f"""
INSERT INTO "{TSHDEOA03_SCHEMA}"."{TSHDEOA03_TABLE}" (
  "기준년월", "그룹회사코드", "그룹고객식별자",
  "직장우편번호코드", "자택우편번호코드",
  "이메일주소보유여부", "휴대폰번호등록여부", "자택전화번호등록여부",
  "직장전화번호등록여부", "푸쉬메시지등록여부",
  "마케팅활용동의계열사수",
  "은행마케팅활용동의여부", "증권마케팅활용동의여부", "손해보험마케팅활용동의여부",
  "카드마케팅활용동의여부", "생명보험마케팅활용동의여부", "캐피탈마케팅활용동의여부",
  "저축은행마케팅활용동의여부",
  "그룹정보제공동의계열사수",
  "은행그룹정보제공동의여부", "증권그룹정보제공동의여부", "손해보험그룹정보제공동의여부",
  "카드그룹정보제공동의여부", "생명그룹정보제공동의여부", "캐피탈그룹정보제공동의여부",
  "저축은행그룹정보제공동의여부"
) VALUES (
  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
"""
