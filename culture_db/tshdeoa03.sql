-- INST1.TSHDEOA03 — 그룹고객 연락처·동의 정보
-- psql 또는 python culture_db/apply_tshdeoa03.py

create schema if not exists "INST1";

create table if not exists "INST1"."TSHDEOA03" (
  "기준년월"                          char(6) not null,
  "그룹회사코드"                      char(3) not null,
  "그룹고객식별자"                    char(10) not null,
  "직장우편번호코드"                  char(3),
  "자택우편번호코드"                  char(3),
  "이메일주소보유여부"                char(1),
  "휴대폰번호등록여부"                char(1),
  "자택전화번호등록여부"              char(1),
  "직장전화번호등록여부"              char(1),
  "푸쉬메시지등록여부"                char(1),
  "마케팅활용동의계열사수"            numeric(3, 0),
  "은행마케팅활용동의여부"            char(1),
  "증권마케팅활용동의여부"            char(1),
  "손해보험마케팅활용동의여부"        char(1),
  "카드마케팅활용동의여부"            char(1),
  "생명보험마케팅활용동의여부"        char(1),
  "캐피탈마케팅활용동의여부"          char(1),
  "저축은행마케팅활용동의여부"        char(1),
  "그룹정보제공동의계열사수"          numeric(3, 0),
  "은행그룹정보제공동의여부"          char(1),
  "증권그룹정보제공동의여부"          char(1),
  "손해보험그룹정보제공동의여부"      char(1),
  "카드그룹정보제공동의여부"          char(1),
  "생명그룹정보제공동의여부"          char(1),
  "캐피탈그룹정보제공동의여부"        char(1),
  "저축은행그룹정보제공동의여부"      char(1),
  constraint "TSHDEOA03_pkey" primary key (
    "기준년월",
    "그룹회사코드",
    "그룹고객식별자"
  )
);

comment on table "INST1"."TSHDEOA03" is 'INST1 스키마 · TSHDEOA03 그룹고객연락처정보';

comment on column "INST1"."TSHDEOA03"."기준년월" is '기준년월 YYYYMM';
comment on column "INST1"."TSHDEOA03"."그룹회사코드" is '금융지주 KFG';
comment on column "INST1"."TSHDEOA03"."그룹고객식별자" is '그룹기준 고객에게 부여되는 고객의 식별자';
comment on column "INST1"."TSHDEOA03"."직장우편번호코드" is '고객의 직장 신우편번호 앞 3자리 정보';
comment on column "INST1"."TSHDEOA03"."자택우편번호코드" is '고객의 자택 신우편번호 앞 3자리 정보';
comment on column "INST1"."TSHDEOA03"."이메일주소보유여부" is '고객의 이메일주소 보유여부';
comment on column "INST1"."TSHDEOA03"."휴대폰번호등록여부" is '고객의 휴대폰번호 등록여부';
comment on column "INST1"."TSHDEOA03"."자택전화번호등록여부" is '고객의 자택전화번호 등록여부';
comment on column "INST1"."TSHDEOA03"."직장전화번호등록여부" is '고객의 직장전화번호 등록여부';
comment on column "INST1"."TSHDEOA03"."푸쉬메시지등록여부" is '고객의 PUSH메시지 등록여부(모바일 푸시 앱알림제어 산출)';
comment on column "INST1"."TSHDEOA03"."마케팅활용동의계열사수" is '해당 고객의 마케팅활용동의 계열사 수';
comment on column "INST1"."TSHDEOA03"."은행마케팅활용동의여부" is '해당 고객의 은행 마케팅활용동의 여부';
comment on column "INST1"."TSHDEOA03"."증권마케팅활용동의여부" is '해당 고객의 증권 마케팅활용동의 여부';
comment on column "INST1"."TSHDEOA03"."손해보험마케팅활용동의여부" is '해당 고객의 손보 마케팅활용동의 여부';
comment on column "INST1"."TSHDEOA03"."카드마케팅활용동의여부" is '해당 고객의 카드 마케팅활용동의 여부';
comment on column "INST1"."TSHDEOA03"."생명보험마케팅활용동의여부" is '해당 고객의 생명 마케팅활용동의 여부';
comment on column "INST1"."TSHDEOA03"."캐피탈마케팅활용동의여부" is '해당 고객의 캐피탈 마케팅활용동의 여부';
comment on column "INST1"."TSHDEOA03"."저축은행마케팅활용동의여부" is '해당 고객의 저축은행 마케팅활용동의 여부';
comment on column "INST1"."TSHDEOA03"."그룹정보제공동의계열사수" is '해당 고객의 그룹정보제공동의 계열사 수';
comment on column "INST1"."TSHDEOA03"."은행그룹정보제공동의여부" is '해당 고객의 은행 그룹정보제공동의 여부';
comment on column "INST1"."TSHDEOA03"."증권그룹정보제공동의여부" is '해당 고객의 증권 그룹정보제공동의 여부';
comment on column "INST1"."TSHDEOA03"."손해보험그룹정보제공동의여부" is '해당 고객의 손보 그룹정보제공동의 여부';
comment on column "INST1"."TSHDEOA03"."카드그룹정보제공동의여부" is '해당 고객의 카드 그룹정보제공동의 여부';
comment on column "INST1"."TSHDEOA03"."생명그룹정보제공동의여부" is '해당 고객의 생명 그룹정보제공동의 여부';
comment on column "INST1"."TSHDEOA03"."캐피탈그룹정보제공동의여부" is '해당 고객의 캐피탈 그룹정보제공동의 여부';
comment on column "INST1"."TSHDEOA03"."저축은행그룹정보제공동의여부" is '해당 고객의 저축은행 그룹정보제공동의 여부';
