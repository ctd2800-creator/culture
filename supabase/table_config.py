"""INST1/public 테이블명 (한글 식별자)."""

TABLE_NAME = "그룹멤버십계열사기초데이터검증"
TABLE_PK_CONSTRAINT = f"{TABLE_NAME}_pkey"

MEMBER_TABLE_NAME = "회원"
MEMBER_PK_CONSTRAINT = f"{MEMBER_TABLE_NAME}_pkey"

TSHDEOA01_SCHEMA = "INST1"
TSHDEOA01_TABLE = "TSHDEOA01"
TSHDEOA01_KOREAN_NAME = "그룹고객기본정보"
TSHDEOA01_FQN = f'{TSHDEOA01_SCHEMA}."{TSHDEOA01_TABLE}"'
TSHDEOA01_PK_CONSTRAINT = "TSHDEOA01_pkey"

# TSHDEOA01 집계 가능 컬럼 (PK·고객식별자 제외)
TSHDEOA01_COLUMNS: tuple[str, ...] = (
    "기준년월",
    "그룹회사코드",
    "그룹고객식별자",
    "당월고객계열사수",
    "활동고객계열사수",
    "핵심고객계열사수",
    "성별구분",
    "연령코드",
    "KB스타클럽그룹본인등급",
    "KB스타클럽그룹최고등급",
    "개인사업자여부",
    "직장인여부",
    "PB고객여부",
    "외국인여부",
)

TSHDEOA01_AGGREGATE_COLUMNS: tuple[str, ...] = (
    "기준년월",
    "그룹회사코드",
    "당월고객계열사수",
    "활동고객계열사수",
    "핵심고객계열사수",
    "성별구분",
    "연령코드",
    "KB스타클럽그룹본인등급",
    "KB스타클럽그룹최고등급",
    "개인사업자여부",
    "직장인여부",
    "PB고객여부",
    "외국인여부",
)

TSHDEOA01_GROUP_ALIASES: dict[str, str] = {
    "스타클럽그룹최고등급": "KB스타클럽그룹최고등급",
    "스타클럽 최고등급": "KB스타클럽그룹최고등급",
    "최고등급": "KB스타클럽그룹최고등급",
    "스타클럽그룹본인등급": "KB스타클럽그룹본인등급",
    "본인등급": "KB스타클럽그룹본인등급",
    "연령": "연령코드",
    "성별": "성별구분",
}

TSHDEOA02_SCHEMA = "INST1"
TSHDEOA02_TABLE = "TSHDEOA02"
TSHDEOA02_KOREAN_NAME = "그룹고객거래기본"
TSHDEOA02_FQN = f'{TSHDEOA02_SCHEMA}."{TSHDEOA02_TABLE}"'
TSHDEOA02_PK_CONSTRAINT = "TSHDEOA02_pkey"

# TSHDEOA02 집계 가능 컬럼 (PK·고객식별자 제외)
TSHDEOA02_COLUMNS: tuple[str, ...] = (
    "기준년월",
    "그룹회사코드",
    "그룹고객식별자",
    "그룹최초거래년월일",
    "그룹최근거래년월일",
    "거래기간구분",
    "창구거래건수",
    "비대면거래건수",
    "최근5년최고수신잔액",
    "최근5년최고여신잔액",
    "수신잔액",
    "여신잔액",
    "보유수신상품계약수",
    "보유여신상품계약수",
    "당월상품신규계약수",
    "당월상품해지계약수",
    "급여이체여부",
    "연금이체여부",
)

TSHDEOA02_AGGREGATE_COLUMNS: tuple[str, ...] = (
    "기준년월",
    "그룹회사코드",
    "그룹최초거래년월일",
    "그룹최근거래년월일",
    "거래기간구분",
    "창구거래건수",
    "비대면거래건수",
    "최근5년최고수신잔액",
    "최근5년최고여신잔액",
    "수신잔액",
    "여신잔액",
    "보유수신상품계약수",
    "보유여신상품계약수",
    "당월상품신규계약수",
    "당월상품해지계약수",
    "급여이체여부",
    "연금이체여부",
)

TSHDEOA02_NUMERIC_COLUMNS: frozenset[str] = frozenset(
    {
        "창구거래건수",
        "비대면거래건수",
        "최근5년최고수신잔액",
        "최근5년최고여신잔액",
        "수신잔액",
        "여신잔액",
        "보유수신상품계약수",
        "보유여신상품계약수",
        "당월상품신규계약수",
        "당월상품해지계약수",
    }
)

TSHDEOA01_NUMERIC_COLUMNS: frozenset[str] = frozenset(
    {
        "당월고객계열사수",
        "활동고객계열사수",
        "핵심고객계열사수",
    }
)

TSHDEOA02_GROUP_ALIASES: dict[str, str] = {
    "거래기간": "거래기간구분",
    "급여이체": "급여이체여부",
    "연금이체": "연금이체여부",
    "신규계약수": "당월상품신규계약수",
    "해지계약수": "당월상품해지계약수",
}

TSHDEOA04_SCHEMA = "INST1"
TSHDEOA04_TABLE = "TSHDEOA04"
TSHDEOA04_KOREAN_NAME = "그룹고객소득대출정보"
TSHDEOA04_FQN = f'{TSHDEOA04_SCHEMA}."{TSHDEOA04_TABLE}"'
TSHDEOA04_PK_CONSTRAINT = "TSHDEOA04_pkey"

TSHDEOA04_COLUMNS: tuple[str, ...] = (
    "기준년월",
    "그룹회사코드",
    "그룹고객식별자",
    "그룹직업분류코드",
    "급여이체여부",
    "급여이체금액",
    "최근3개월급여이체평균금액",
    "연소득금액",
    "연본인근로소득",
    "연본인사업소득",
    "그룹총대출잔액",
    "그룹연체잔액",
    "그룹최대연체일수",
)

TSHDEOA04_AGGREGATE_COLUMNS: tuple[str, ...] = (
    "기준년월",
    "그룹회사코드",
    "그룹직업분류코드",
    "급여이체여부",
    "급여이체금액",
    "최근3개월급여이체평균금액",
    "연소득금액",
    "연본인근로소득",
    "연본인사업소득",
    "그룹총대출잔액",
    "그룹연체잔액",
    "그룹최대연체일수",
)

TSHDEOA04_NUMERIC_COLUMNS: frozenset[str] = frozenset(
    {
        "급여이체금액",
        "최근3개월급여이체평균금액",
        "연소득금액",
        "연본인근로소득",
        "연본인사업소득",
        "그룹총대출잔액",
        "그룹연체잔액",
        "그룹최대연체일수",
    }
)

TSHDEOA04_GROUP_ALIASES: dict[str, str] = {
    "직업분류": "그룹직업분류코드",
    "급여이체": "급여이체여부",
    "연소득": "연소득금액",
    "근로소득": "연본인근로소득",
    "사업소득": "연본인사업소득",
    "대출잔액": "그룹총대출잔액",
    "연체잔액": "그룹연체잔액",
    "연체일수": "그룹최대연체일수",
}

INST1_AGGREGATE_COLUMNS: dict[str, tuple[str, ...]] = {
    TSHDEOA01_TABLE: TSHDEOA01_AGGREGATE_COLUMNS,
    TSHDEOA02_TABLE: TSHDEOA02_AGGREGATE_COLUMNS,
    TSHDEOA04_TABLE: TSHDEOA04_AGGREGATE_COLUMNS,
}

INST1_GROUP_ALIASES: dict[str, dict[str, str]] = {
    TSHDEOA01_TABLE: TSHDEOA01_GROUP_ALIASES,
    TSHDEOA02_TABLE: TSHDEOA02_GROUP_ALIASES,
    TSHDEOA04_TABLE: TSHDEOA04_GROUP_ALIASES,
}

INST1_NUMERIC_COLUMNS: dict[str, frozenset[str]] = {
    TSHDEOA01_TABLE: TSHDEOA01_NUMERIC_COLUMNS,
    TSHDEOA02_TABLE: TSHDEOA02_NUMERIC_COLUMNS,
    TSHDEOA04_TABLE: TSHDEOA04_NUMERIC_COLUMNS,
}

# TSHDEOA01·TSHDEOA02 조인 키
INST1_JOIN_KEYS: tuple[str, ...] = ("기준년월", "그룹회사코드", "그룹고객식별자")

INST1_TABLE_ORDER: tuple[str, ...] = (TSHDEOA01_TABLE, TSHDEOA02_TABLE, TSHDEOA04_TABLE)

INST1_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    TSHDEOA01_TABLE: TSHDEOA01_COLUMNS,
    TSHDEOA02_TABLE: TSHDEOA02_COLUMNS,
    TSHDEOA04_TABLE: TSHDEOA04_COLUMNS,
}

INST1_TABLE_KOREAN_NAMES: dict[str, str] = {
    TSHDEOA01_TABLE: TSHDEOA01_KOREAN_NAME,
    TSHDEOA02_TABLE: TSHDEOA02_KOREAN_NAME,
    TSHDEOA04_TABLE: TSHDEOA04_KOREAN_NAME,
}

INST1_TABLE_SQL_ALIAS: dict[str, str] = {
    TSHDEOA01_TABLE: "a01",
    TSHDEOA02_TABLE: "a02",
    TSHDEOA04_TABLE: "a04",
}

INST1_TABLE_ALIASES: dict[str, tuple[str, ...]] = {
    TSHDEOA01_TABLE: (
        TSHDEOA01_KOREAN_NAME,
        "그룹 고객 기본정보",
        "그룹고객 기본정보",
    ),
    TSHDEOA02_TABLE: (
        TSHDEOA02_KOREAN_NAME,
        "그룹 고객 거래기본",
        "그룹고객 거래기본",
    ),
    TSHDEOA04_TABLE: (
        TSHDEOA04_KOREAN_NAME,
        "그룹 고객 소득대출정보",
        "그룹고객 소득대출정보",
        "소득대출",
    ),
}

TSHDE0ZCD_SCHEMA = "INST1"
TSHDE0ZCD_TABLE = "TSHDE0ZCD"
TSHDE0ZCD_KOREAN_NAME = "그룹고객분석인스턴스목록"
TSHDE0ZCD_FQN = f'{TSHDE0ZCD_SCHEMA}."{TSHDE0ZCD_TABLE}"'
TSHDE0ZCD_PK_CONSTRAINT = "TSHDE0ZCD_pkey"

TSHDE0ZCD_COLUMNS: tuple[str, ...] = (
    "그룹회사코드",
    "인스턴스식별자",
    "인스턴스코드",
    "유효시작년월일",
    "유효종료년월일",
    "인스턴스명",
    "인스턴스내용",
    "그룹최초등록일시",
    "그룹최종변경일시",
)

INST1_TABLE_COLUMNS[TSHDE0ZCD_TABLE] = TSHDE0ZCD_COLUMNS
INST1_TABLE_KOREAN_NAMES[TSHDE0ZCD_TABLE] = TSHDE0ZCD_KOREAN_NAME
INST1_TABLE_ALIASES[TSHDE0ZCD_TABLE] = (
    TSHDE0ZCD_KOREAN_NAME,
    "그룹 고객 분석 인스턴스 목록",
    "인스턴스목록",
)

# INST1 스키마 테이블 — UI 「분석가능 테이블」 표시 순서 (테이블명, 한글명)
INST1_SCHEMA_TABLES: tuple[tuple[str, str], ...] = (
    (TSHDEOA01_TABLE, TSHDEOA01_KOREAN_NAME),
    (TSHDEOA02_TABLE, TSHDEOA02_KOREAN_NAME),
    (TSHDEOA04_TABLE, TSHDEOA04_KOREAN_NAME),
)


def inst1_table_display_label(table_name: str, korean_name: str | None = None) -> str:
    korean = korean_name or INST1_TABLE_KOREAN_NAMES.get(table_name, table_name)
    return f"{korean}({table_name})"


def inst1_schema_table_display_items() -> list[dict[str, str]]:
    return [
        {
            "table": table,
            "korean": korean,
            "label": inst1_table_display_label(table, korean),
        }
        for table, korean in INST1_SCHEMA_TABLES
    ]

# 컬럼명 → TSHDE0ZCD 인스턴스식별자
COLUMN_INSTANCE_IDS: dict[str, str] = {
    "그룹회사코드": "0036",
    "성별구분": "101644000",
    "연령코드": "116252000",
    "KB스타클럽그룹본인등급": "100243000",
    "KB스타클럽그룹최고등급": "100243000",
    "개인사업자여부": "102132000",
    "직장인여부": "102132000",
    "PB고객여부": "102132000",
    "외국인여부": "102132000",
    "거래기간구분": "106308000",
    "급여이체여부": "102132000",
    "연금이체여부": "102132000",
    "그룹직업분류코드": "132648000",
}

# 채팅 요약 요청 시 테이블을 가리키는 표현
TABLE_QUERY_KEYWORDS = (
    "TCHDHC001",
    "TCHDHC",
    "그룹멤버십계열사기초데이터검증",
    "그룹멤버십",
    "계열사기초데이터검증",
    "기초데이터검증",
    "TSHDEOA01",
    "그룹고객기본정보",
    "TSHDEOA02",
    "그룹고객거래기본",
    "TSHDEOA04",
    "TSHDE0A04",
    "그룹고객소득대출정보",
    "TSHDE0ZCD",
    "TSHDEO",
)
