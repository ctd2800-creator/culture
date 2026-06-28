"""INST1.TSHDE0ZCD 인스턴스 코드 시드."""

from __future__ import annotations

from culture_db.table_config import TSHDE0ZCD_SCHEMA, TSHDE0ZCD_TABLE

_TS_AGE = "2019-11-26 00:00:00"
_TS_TRADE = "2010-02-01 00:00:00"
_TS_KFG = "2020-07-20 10:04:06"
_TS_KP0 = "2021-06-02 14:45:14"
_TS_CODE = "2010-02-01 00:00:00"
_TS_JOB = "2018-03-21 00:00:00"

_TRADE_PERIOD_LABELS: dict[int, str] = {
    0: "해당무",
    1: "01개월이하",
    2: "02개월이하",
    3: "03개월이하",
    4: "04개월이하",
    5: "05개월이하",
    6: "06개월이하",
    7: "07개월이하",
    8: "08개월이하",
    9: "09개월이하",
    10: "10개월이하",
    11: "11개월이하",
    12: "12개월이하",
    13: "01년이상",
    14: "05년이상",
    15: "10년이상",
    16: "15년이상",
    17: "20년이상",
    18: "25년이상",
}

TSHDE0ZCD_AGE_ROWS: list[tuple] = [
    (
        "K00",
        "116252000",
        f"{age:03d}",
        "20191126",
        "99991231",
        "연령코드",
        f"{age}세",
        _TS_AGE,
        _TS_AGE,
    )
    for age in range(0, 72)
]

TSHDE0ZCD_TRADE_PERIOD_ROWS: list[tuple] = [
    (
        "K00",
        "106308000",
        f"{code:02d}",
        "20100201",
        "99991231",
        "거래기간구분코드",
        _TRADE_PERIOD_LABELS[code],
        _TS_TRADE,
        _TS_TRADE,
    )
    for code in range(0, 19)
]

TSHDE0ZCD_GROUP_COMPANY_ROWS: list[tuple] = [
    ("KFG", "0036", code, "20200716", "99991231", "FG그룹DB그룹회사코드", label, ts, ts)
    for code, label, ts in (
        ("KB0", "KB국민은행", _TS_KFG),
        ("KC0", "KB국민카드", _TS_KFG),
        ("KFG", "KB금융그룹", _TS_KFG),
        ("KL0", "KB캐피탈", _TS_KFG),
        ("KM0", "KB저축은행", _TS_KFG),
        ("KN0", "KB생명보험", _TS_KFG),
        ("KN1", "KB손해보험", _TS_KFG),
        ("KP0", "푸르덴셜생명", _TS_KP0),
        ("KS2", "KB증권", _TS_KFG),
    )
]

TSHDE0ZCD_CUSTOMER_TYPE_ROWS: list[tuple] = [
    (
        "K00",
        "100243000",
        code,
        "20100201",
        "99991231",
        "고객구분코드",
        label,
        _TS_CODE,
        _TS_CODE,
    )
    for code, label in (
        ("0", "해당무"),
        ("1", "VVIP"),
        ("2", "VIP"),
        ("3", "그랜드"),
        ("4", "우대(2004년07월이전)"),
        ("5", "베스트"),
        ("6", "잠재고객"),
        ("9", "패밀리"),
    )
]

TSHDE0ZCD_GENDER_ROWS: list[tuple] = [
    (
        "K00",
        "101644000",
        code,
        "20100201",
        "99991231",
        "성별구분코드",
        label,
        _TS_CODE,
        _TS_CODE,
    )
    for code, label in (("0", "해당무"), ("1", "남자"), ("2", "여자"))
]

TSHDE0ZCD_YN_ROWS: list[tuple] = [
    (
        "K00",
        "102132000",
        code,
        "20100201",
        "99991231",
        "여부",
        label,
        _TS_CODE,
        _TS_CODE,
    )
    for code, label in (("0", "부"), ("1", "여"))
]

TSHDE0ZCD_JOB_CLASS_ROWS: list[tuple] = [
    (
        "KFG",
        "132648000",
        code,
        "20180321",
        "99991231",
        "FG그룹직업분류코드",
        label,
        _TS_JOB,
        _TS_JOB,
    )
    for code, label in (
        ("1", "공무원(공공기관,군인 등 포함)"),
        ("2", "직장인"),
        ("3", "전문직"),
        ("4", "자영업자"),
        ("5", "학생(대학원)"),
        ("6", "주부"),
        ("7", "연금(임대소득자)"),
        ("9", "기타"),
    )
]

TSHDE0ZCD_ROWS: list[tuple] = (
    TSHDE0ZCD_AGE_ROWS
    + TSHDE0ZCD_TRADE_PERIOD_ROWS
    + TSHDE0ZCD_GROUP_COMPANY_ROWS
    + TSHDE0ZCD_CUSTOMER_TYPE_ROWS
    + TSHDE0ZCD_GENDER_ROWS
    + TSHDE0ZCD_YN_ROWS
    + TSHDE0ZCD_JOB_CLASS_ROWS
)

TSHDE0ZCD_UPSERT_SQL = f"""
INSERT INTO "{TSHDE0ZCD_SCHEMA}"."{TSHDE0ZCD_TABLE}" (
  "그룹회사코드", "인스턴스식별자", "인스턴스코드", "유효시작년월일",
  "유효종료년월일", "인스턴스명", "인스턴스내용",
  "그룹최초등록일시", "그룹최종변경일시"
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT ("그룹회사코드", "인스턴스식별자", "인스턴스코드", "유효시작년월일")
DO UPDATE SET
  "유효종료년월일" = EXCLUDED."유효종료년월일",
  "인스턴스명" = EXCLUDED."인스턴스명",
  "인스턴스내용" = EXCLUDED."인스턴스내용",
  "그룹최초등록일시" = EXCLUDED."그룹최초등록일시",
  "그룹최종변경일시" = EXCLUDED."그룹최종변경일시";
"""
