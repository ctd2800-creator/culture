"""INST1/public 테이블명 (한글 식별자)."""

MEMBER_TABLE_NAME = "회원"
MEMBER_PK_CONSTRAINT = f"{MEMBER_TABLE_NAME}_pkey"

QUESTION_LOG_TABLE_NAME = "질문내역"
QUESTION_LOG_PK_CONSTRAINT = f"{QUESTION_LOG_TABLE_NAME}_pkey"

USER_PERMISSION_TABLE_NAME = "유저권한"
USER_PERMISSION_PK_CONSTRAINT = f"{USER_PERMISSION_TABLE_NAME}_pkey"

# 삭제·폐기 테이블 — DB/OpenSearch 스키마 검색·인덱싱에서 제외
LEGACY_EXCLUDED_TABLES: frozenset[str] = frozenset({
    "calendar",
    "info",
    "그룹멤버십계열사기초데이터검증",
})

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
    "KB스타클럽등급": "KB스타클럽그룹최고등급",
    "스타클럽등급": "KB스타클럽그룹최고등급",
    "스타클럽 등급": "KB스타클럽그룹최고등급",
    "스타클럽그룹등급": "KB스타클럽그룹최고등급",
    "스타클럽 그룹등급": "KB스타클럽그룹최고등급",
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

TSHDEOA03_SCHEMA = "INST1"
TSHDEOA03_TABLE = "TSHDEOA03"
TSHDEOA03_KOREAN_NAME = "그룹고객연락처정보"
TSHDEOA03_FQN = f'{TSHDEOA03_SCHEMA}."{TSHDEOA03_TABLE}"'
TSHDEOA03_PK_CONSTRAINT = "TSHDEOA03_pkey"

TSHDEOA03_COLUMNS: tuple[str, ...] = (
    "기준년월",
    "그룹회사코드",
    "그룹고객식별자",
    "직장우편번호코드",
    "자택우편번호코드",
    "이메일주소보유여부",
    "휴대폰번호등록여부",
    "자택전화번호등록여부",
    "직장전화번호등록여부",
    "푸쉬메시지등록여부",
    "마케팅활용동의계열사수",
    "은행마케팅활용동의여부",
    "증권마케팅활용동의여부",
    "손해보험마케팅활용동의여부",
    "카드마케팅활용동의여부",
    "생명보험마케팅활용동의여부",
    "캐피탈마케팅활용동의여부",
    "저축은행마케팅활용동의여부",
    "그룹정보제공동의계열사수",
    "은행그룹정보제공동의여부",
    "증권그룹정보제공동의여부",
    "손해보험그룹정보제공동의여부",
    "카드그룹정보제공동의여부",
    "생명그룹정보제공동의여부",
    "캐피탈그룹정보제공동의여부",
    "저축은행그룹정보제공동의여부",
)

TSHDEOA03_AGGREGATE_COLUMNS: tuple[str, ...] = (
    "기준년월",
    "그룹회사코드",
    "직장우편번호코드",
    "자택우편번호코드",
    "이메일주소보유여부",
    "휴대폰번호등록여부",
    "자택전화번호등록여부",
    "직장전화번호등록여부",
    "푸쉬메시지등록여부",
    "마케팅활용동의계열사수",
    "은행마케팅활용동의여부",
    "증권마케팅활용동의여부",
    "손해보험마케팅활용동의여부",
    "카드마케팅활용동의여부",
    "생명보험마케팅활용동의여부",
    "캐피탈마케팅활용동의여부",
    "저축은행마케팅활용동의여부",
    "그룹정보제공동의계열사수",
    "은행그룹정보제공동의여부",
    "증권그룹정보제공동의여부",
    "손해보험그룹정보제공동의여부",
    "카드그룹정보제공동의여부",
    "생명그룹정보제공동의여부",
    "캐피탈그룹정보제공동의여부",
    "저축은행그룹정보제공동의여부",
)

TSHDEOA03_NUMERIC_COLUMNS: frozenset[str] = frozenset(
    {"마케팅활용동의계열사수", "그룹정보제공동의계열사수"}
)

TSHDEOA03_GROUP_ALIASES: dict[str, str] = {
    "이메일": "이메일주소보유여부",
    "휴대폰": "휴대폰번호등록여부",
    "푸시": "푸쉬메시지등록여부",
    "마케팅동의": "마케팅활용동의계열사수",
}

TSHDEOA05_SCHEMA = "INST1"
TSHDEOA05_TABLE = "TSHDEOA05"
TSHDEOA05_KOREAN_NAME = "그룹계열사마케팅정보"
TSHDEOA05_FQN = f'{TSHDEOA05_SCHEMA}."{TSHDEOA05_TABLE}"'
TSHDEOA05_PK_CONSTRAINT = "TSHDEOA05_pkey"

TSHDEOA05_COLUMNS: tuple[str, ...] = (
    "기준년월",
    "정보제공동의계열사구분내용",
    "그룹고객식별자",
    "계열사마케팅동의여부",
    "계열사마케팅동의년월일",
    "계열사마케팅동의종료예정년월일",
)

TSHDEOA05_AGGREGATE_COLUMNS: tuple[str, ...] = (
    "기준년월",
    "정보제공동의계열사구분내용",
    "계열사마케팅동의여부",
    "계열사마케팅동의년월일",
    "계열사마케팅동의종료예정년월일",
)

TSHDEOA05_NUMERIC_COLUMNS: frozenset[str] = frozenset()
TSHDEOA05_GROUP_ALIASES: dict[str, str] = {
    "계열사구분": "정보제공동의계열사구분내용",
    "마케팅동의": "계열사마케팅동의여부",
}

TSHDEOA06_SCHEMA = "INST1"
TSHDEOA06_TABLE = "TSHDEOA06"
TSHDEOA06_KOREAN_NAME = "그룹신용등급정보"
TSHDEOA06_FQN = f'{TSHDEOA06_SCHEMA}."{TSHDEOA06_TABLE}"'
TSHDEOA06_PK_CONSTRAINT = "TSHDEOA06_pkey"

TSHDEOA06_COLUMNS: tuple[str, ...] = (
    "기준년월",
    "그룹회사코드",
    "그룹고객식별자",
    "세그먼트분류명",
    "실적평점",
    "일반평점",
    "결합평점",
    "통합등급내용",
)

TSHDEOA06_AGGREGATE_COLUMNS: tuple[str, ...] = (
    "기준년월",
    "그룹회사코드",
    "세그먼트분류명",
    "실적평점",
    "일반평점",
    "결합평점",
    "통합등급내용",
)

TSHDEOA06_NUMERIC_COLUMNS: frozenset[str] = frozenset(
    {"실적평점", "일반평점", "결합평점"}
)

TSHDEOA06_GROUP_ALIASES: dict[str, str] = {
    "세그먼트": "세그먼트분류명",
    "신용등급": "통합등급내용",
    "결합평가": "결합평점",
}

INST1_AGGREGATE_COLUMNS: dict[str, tuple[str, ...]] = {
    TSHDEOA01_TABLE: TSHDEOA01_AGGREGATE_COLUMNS,
    TSHDEOA02_TABLE: TSHDEOA02_AGGREGATE_COLUMNS,
    TSHDEOA03_TABLE: TSHDEOA03_AGGREGATE_COLUMNS,
    TSHDEOA04_TABLE: TSHDEOA04_AGGREGATE_COLUMNS,
    TSHDEOA05_TABLE: TSHDEOA05_AGGREGATE_COLUMNS,
    TSHDEOA06_TABLE: TSHDEOA06_AGGREGATE_COLUMNS,
}

INST1_GROUP_ALIASES: dict[str, dict[str, str]] = {
    TSHDEOA01_TABLE: TSHDEOA01_GROUP_ALIASES,
    TSHDEOA02_TABLE: TSHDEOA02_GROUP_ALIASES,
    TSHDEOA03_TABLE: TSHDEOA03_GROUP_ALIASES,
    TSHDEOA04_TABLE: TSHDEOA04_GROUP_ALIASES,
    TSHDEOA05_TABLE: TSHDEOA05_GROUP_ALIASES,
    TSHDEOA06_TABLE: TSHDEOA06_GROUP_ALIASES,
}

INST1_NUMERIC_COLUMNS: dict[str, frozenset[str]] = {
    TSHDEOA01_TABLE: TSHDEOA01_NUMERIC_COLUMNS,
    TSHDEOA02_TABLE: TSHDEOA02_NUMERIC_COLUMNS,
    TSHDEOA03_TABLE: TSHDEOA03_NUMERIC_COLUMNS,
    TSHDEOA04_TABLE: TSHDEOA04_NUMERIC_COLUMNS,
    TSHDEOA05_TABLE: TSHDEOA05_NUMERIC_COLUMNS,
    TSHDEOA06_TABLE: TSHDEOA06_NUMERIC_COLUMNS,
}

# TSHDEOA01·TSHDEOA02 조인 키
INST1_JOIN_KEYS: tuple[str, ...] = ("기준년월", "그룹회사코드", "그룹고객식별자")

INST1_DATA_TABLES: frozenset[str] = frozenset(
    {
        TSHDEOA01_TABLE,
        TSHDEOA02_TABLE,
        TSHDEOA03_TABLE,
        TSHDEOA04_TABLE,
        TSHDEOA05_TABLE,
        TSHDEOA06_TABLE,
    }
)


def inst1_table_has_group_company(table: str) -> bool:
    return "그룹회사코드" in INST1_TABLE_COLUMNS.get(table, ())


# 고객당(기준년월·그룹회사코드·그룹고객식별자) 정확히 1행이 보장되는 테이블.
# 이 테이블들끼리 조인하면 그룹고객식별자 기준 1:1이라 fan-out이 없고,
# COUNT(DISTINCT "그룹고객식별자") == COUNT("그룹고객식별자") 가 성립한다.
# TSHDEOA05는 PK가 (기준년월, 정보제공동의계열사구분내용, 그룹고객식별자)라
# 한 고객이 월에 여러 행을 가질 수 있어 제외한다(조인 시 DISTINCT 필요).
INST1_CUSTOMER_UNIQUE_TABLES: frozenset[str] = frozenset(
    {
        TSHDEOA01_TABLE,
        TSHDEOA02_TABLE,
        TSHDEOA03_TABLE,
        TSHDEOA04_TABLE,
        TSHDEOA06_TABLE,
    }
)


def inst1_table_customer_unique(table: str) -> bool:
    """해당 테이블이 (기준년월·그룹회사코드·그룹고객식별자)당 1행인지 여부."""
    return table in INST1_CUSTOMER_UNIQUE_TABLES


def inst1_join_is_customer_unique(tables) -> bool:
    """조인에 참여한 모든 테이블이 고객당 1행이면 True (fan-out 없음)."""
    return all(inst1_table_customer_unique(t) for t in tables)


def inst1_join_keys_between(table_a: str, table_b: str) -> tuple[str, ...]:
    cols_a = set(INST1_TABLE_COLUMNS.get(table_a, ()))
    cols_b = set(INST1_TABLE_COLUMNS.get(table_b, ()))
    return tuple(k for k in INST1_JOIN_KEYS if k in cols_a and k in cols_b)

INST1_TABLE_ORDER: tuple[str, ...] = (
    TSHDEOA01_TABLE,
    TSHDEOA02_TABLE,
    TSHDEOA03_TABLE,
    TSHDEOA04_TABLE,
    TSHDEOA05_TABLE,
    TSHDEOA06_TABLE,
)

INST1_TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    TSHDEOA01_TABLE: TSHDEOA01_COLUMNS,
    TSHDEOA02_TABLE: TSHDEOA02_COLUMNS,
    TSHDEOA03_TABLE: TSHDEOA03_COLUMNS,
    TSHDEOA04_TABLE: TSHDEOA04_COLUMNS,
    TSHDEOA05_TABLE: TSHDEOA05_COLUMNS,
    TSHDEOA06_TABLE: TSHDEOA06_COLUMNS,
}

INST1_TABLE_KOREAN_NAMES: dict[str, str] = {
    TSHDEOA01_TABLE: TSHDEOA01_KOREAN_NAME,
    TSHDEOA02_TABLE: TSHDEOA02_KOREAN_NAME,
    TSHDEOA03_TABLE: TSHDEOA03_KOREAN_NAME,
    TSHDEOA04_TABLE: TSHDEOA04_KOREAN_NAME,
    TSHDEOA05_TABLE: TSHDEOA05_KOREAN_NAME,
    TSHDEOA06_TABLE: TSHDEOA06_KOREAN_NAME,
}

INST1_TABLE_SQL_ALIAS: dict[str, str] = {
    TSHDEOA01_TABLE: "a01",
    TSHDEOA02_TABLE: "a02",
    TSHDEOA03_TABLE: "a03",
    TSHDEOA04_TABLE: "a04",
    TSHDEOA05_TABLE: "a05",
    TSHDEOA06_TABLE: "a06",
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
    TSHDEOA03_TABLE: (
        TSHDEOA03_KOREAN_NAME,
        "그룹 고객 연락처정보",
        "그룹고객 연락처정보",
        "연락처",
        "마케팅동의",
    ),
    TSHDEOA04_TABLE: (
        TSHDEOA04_KOREAN_NAME,
        "그룹 고객 소득대출정보",
        "그룹고객 소득대출정보",
        "소득대출",
    ),
    TSHDEOA05_TABLE: (
        TSHDEOA05_KOREAN_NAME,
        "그룹 계열사 마케팅정보",
        "그룹계열사 마케팅정보",
        "계열사마케팅",
    ),
    TSHDEOA06_TABLE: (
        TSHDEOA06_KOREAN_NAME,
        "그룹 신용등급정보",
        "그룹고객 신용등급",
        "신용등급",
        "세그먼트",
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
    (TSHDEOA03_TABLE, TSHDEOA03_KOREAN_NAME),
    (TSHDEOA04_TABLE, TSHDEOA04_KOREAN_NAME),
    (TSHDEOA05_TABLE, TSHDEOA05_KOREAN_NAME),
    (TSHDEOA06_TABLE, TSHDEOA06_KOREAN_NAME),
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

# 테이블별 컬럼정의내용 (데이터 사전·OpenSearch·채팅 컬럼 설명)
INST1_COLUMN_DEFINITIONS: dict[str, dict[str, str]] = {
    TSHDEOA01_TABLE: {
        "기준년월": "기준년월 YYYYMM",
        "그룹회사코드": "금융지주 KFG",
        "그룹고객식별자": "그룹고객식별자",
        "당월고객계열사수": (
            "해당 금융기관 고객으로 산정되는 고객 전체 "
            "캐피탈사 고객정의 변경으로 (2022.12~2025.05) TSHDE6A01 당월고객여부2 사용"
        ),
        "활동고객계열사수": (
            "[은/증/손/카/푸/캐/생/저] 8개 계열사 중 활동고객인 계열사 수 "
            "캐피탈사 고객정의 변경으로 (2022.12~2025.05) TSHDE6A01 활동고객여부2 사용"
        ),
        "핵심고객계열사수": "[은/증/손/카/푸/캐/생/저] 8개 계열사 중 핵심고객인 계열사 수",
        "성별구분": "고객의 성별 0 : 해당무 1 : 남자 2 : 여자",
        "연령코드": (
            "고객의 연령으로 10단위로 만 나이기준으로 산출 "
            "그룹연령구분코드 001 1세 002 2세 003 3세 004 4세 005 5세 "
            "...... 110 110세이상 999 연령미상"
        ),
        "KB스타클럽그룹본인등급": (
            "KB스타클럽 그룹등급구분 1: VVIP, 2: VIP, 3: 그랜드, 5: 베스트, 9: 패밀리 "
            "(2023년 6월부터 적용) ※ 단, 2023년 5월까지는 "
            "1: MVP, 2: 로얄, 3: 골드, 5: 프리미엄, 9: 일반으로 적용"
        ),
        "KB스타클럽그룹최고등급": (
            "KB스타클럽 그룹등급구분 1: VVIP, 2: VIP, 3: 그랜드, 5: 베스트, 9: 패밀리 "
            "(2023년 6월부터 적용) ※ 단, 2023년 5월까지는 "
            "1: MVP, 2: 로얄, 3: 골드, 5: 프리미엄, 9: 일반으로 적용"
        ),
        "개인사업자여부": "개인사업자(SOHO)여부 0 : 해당무 1 : 개인사업자",
        "직장인여부": "직장인 여부 0 : 해당무 1 : 직장인",
        "PB고객여부": "PB고객인지 여부 0 : 해당무 1 : PB고객",
        "외국인여부": "외국인고객인지 여부 0 : 해당무 1 : 외국인",
    },
    TSHDEOA02_TABLE: {
        "기준년월": "기준년월 YYYYMM",
        "그룹회사코드": '금융지주 "KFG"',
        "그룹고객식별자": "그룹기준 고객에게 부여되는 고객의 식별자",
        "그룹최초거래년월일": "CIF(고객정보) 최초등록일 또는 최초계좌신규일",
        "그룹최근거래년월일": "고객이 보유한 계좌의 최종거래일",
        "거래기간구분": (
            "고객이 KB금융그룹과 거래한 기간구분 "
            "그룹거래기간구분코드 00 해당무 01 01개월이하 02 02개월이하 "
            "... 12 12개월이하 13 01년이상 14 05년이상 15 10년이상 16 15년이상 17 20년이상"
        ),
        "창구거래건수": "고객의 기준월 창구거래건수",
        "비대면거래건수": "고객의 기준월 비대면거래건수",
        "최근5년최고수신잔액": "최근 5년내 월별 수신잔액중 최고금액",
        "최근5년최고여신잔액": "최근 5년내 월별 여신잔액중 최고금액",
        "수신잔액": "기준월말 수신잔액",
        "여신잔액": "기준월말 여신잔액",
        "보유수신상품계약수": "기준월말 정상 수신계좌수",
        "보유여신상품계약수": "기준월말 정상 여신계좌수",
        "당월상품신규계약수": "기준월 신규상품 계좌수",
        "당월상품해지계약수": "기준월 해지상품 계좌수",
        "급여이체여부": "고객의 기준월 급여이체여부",
        "연금이체여부": (
            "고객의 기준월 연금(국민연금, 군인연금, 사학연금, 공무원연금) 이체여부"
        ),
    },
    TSHDEOA04_TABLE: {
        "기준년월": "기준년월 YYYYMM",
        "그룹회사코드": "금융지주 KFG",
        "그룹고객식별자": "그룹고객식별자",
        "그룹직업분류코드": (
            "그룹직업구분에 따른 고객의 직업, 그룹직업구분코드 (별도생성)"
        ),
        "급여이체여부": "고객의 급여이체 고객여부",
        "급여이체금액": "고객의 기준월 급여이체금액",
        "최근3개월급여이체평균금액": "고객의 최근3개월 급여이체평균금액",
        "연소득금액": "고객의 연소득금액",
        "연본인근로소득": "고객의 연본인근로소득",
        "연본인사업소득": "고객의 연본인사업소득",
        "그룹총대출잔액": "고객의 여신계약금액 합산",
        "그룹연체잔액": "고객의 연체잔액 합산",
        "그룹최대연체일수": "고객의 최장연체일수",
    },
    TSHDEOA03_TABLE: {
        "기준년월": "기준년월 YYYYMM",
        "그룹회사코드": '금융지주 "KFG"',
        "그룹고객식별자": "그룹기준 고객에게 부여되는 고객의 식별자",
        "직장우편번호코드": "고객의 직장 신우편번호 앞 3자리 정보",
        "자택우편번호코드": "고객의 자택 신우편번호 앞 3자리 정보",
        "이메일주소보유여부": "고객의 이메일주소 보유여부",
        "휴대폰번호등록여부": "고객의 휴대폰번호 등록여부",
        "자택전화번호등록여부": "고객의 자택전화번호 등록여부",
        "직장전화번호등록여부": "고객의 직장전화번호 등록여부",
        "푸쉬메시지등록여부": "고객의 PUSH메시지 등록여부(모바일 푸시 앱알림제어 산출)",
        "마케팅활용동의계열사수": "해당 고객의 마케팅활용동의 계열사 수",
        "은행마케팅활용동의여부": "해당 고객의 은행 마케팅활용동의 여부",
        "증권마케팅활용동의여부": "해당 고객의 증권 마케팅활용동의 여부",
        "손해보험마케팅활용동의여부": "해당 고객의 손보 마케팅활용동의 여부",
        "카드마케팅활용동의여부": "해당 고객의 카드 마케팅활용동의 여부",
        "생명보험마케팅활용동의여부": "해당 고객의 생명 마케팅활용동의 여부",
        "캐피탈마케팅활용동의여부": "해당 고객의 캐피탈 마케팅활용동의 여부",
        "저축은행마케팅활용동의여부": "해당 고객의 저축은행 마케팅활용동의 여부",
        "그룹정보제공동의계열사수": "해당 고객의 그룹정보제공동의 계열사 수",
        "은행그룹정보제공동의여부": "해당 고객의 은행 그룹정보제공동의 여부",
        "증권그룹정보제공동의여부": "해당 고객의 증권 그룹정보제공동의 여부",
        "손해보험그룹정보제공동의여부": "해당 고객의 손보 그룹정보제공동의 여부",
        "카드그룹정보제공동의여부": "해당 고객의 카드 그룹정보제공동의 여부",
        "생명그룹정보제공동의여부": "해당 고객의 생명 그룹정보제공동의 여부",
        "캐피탈그룹정보제공동의여부": "해당 고객의 캐피탈 그룹정보제공동의 여부",
        "저축은행그룹정보제공동의여부": "해당 고객의 저축은행 그룹정보제공동의 여부",
    },
    TSHDEOA05_TABLE: {
        "기준년월": "기준년월",
        "정보제공동의계열사구분내용": "원 그룹계열회사구분값",
        "그룹고객식별자": (
            "그룹고객식별자 (계열사별 앱으로 회원 고객정보를 "
            "그룹에서 그룹고객식별자로 변환작업필요)"
        ),
        "계열사마케팅동의여부": "해당 테이블은 동의한 고객만 적재",
        "계열사마케팅동의년월일": "계열사마케팅정보제공동의일자",
        "계열사마케팅동의종료예정년월일": "계열사마케팅정보제공동의 종료 예정일",
    },
    TSHDEOA06_TABLE: {
        "기준년월": "기준년월",
        "그룹회사코드": "금융지주 KFG",
        "그룹고객식별자": (
            "그룹고객식별자 (계열사별 암호화된 고객번호를 "
            "그룹에서 그룹고객식별자로 변환작업필요)"
        ),
        "세그먼트분류명": (
            "SEG1 - 과거 6개월 내 대출보유/SEG2 - 과거 6개월 내 대출 미보유 및 "
            "신용카드 보유/SEG3 - 과거 6개월 내 대출 미보유 및 체크카드 보유"
        ),
        "실적평점": "그룹통합 실적모형 평점(지주사 제공)",
        "일반평점": "그룹통합 일반모형 평점 (KCB 제공)",
        "결합평점": "그룹통합 소매신용평점 (SEG별 결합가중치 적용)",
        "통합등급내용": "그룹통합 소매신용등급 (결합평점별 등급구간 적용)",
    },
}

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
    "TSHDEOA01",
    "그룹고객기본정보",
    "TSHDEOA02",
    "그룹고객거래기본",
    "TSHDEOA03",
    "TSHDE0A03",
    "그룹고객연락처정보",
    "TSHDEOA04",
    "TSHDE0A04",
    "그룹고객소득대출정보",
    "TSHDEOA05",
    "TSHDE0A05",
    "그룹계열사마케팅정보",
    "TSHDEOA06",
    "TSHDE0A06",
    "그룹신용등급정보",
    "TSHDE0ZCD",
    "TSHDEO",
)
