-- INST1.TSHDEOA01 — 그룹 고객 기본 속성 (메타데이터 명세 기반)
-- psql 또는 python culture_db/apply_tshdeoa01.py

create schema if not exists "INST1";

create table if not exists "INST1"."TSHDEOA01" (
  "기준년월"                  char(6) not null,
  "그룹회사코드"              char(3) not null,
  "그룹고객식별자"            char(10) not null,
  "당월고객계열사수"          numeric(3, 0),
  "활동고객계열사수"          numeric(3, 0),
  "핵심고객계열사수"          numeric(3, 0),
  "성별구분"                  char(1),
  "연령코드"                  char(3),
  "KB스타클럽그룹본인등급"    char(1),
  "KB스타클럽그룹최고등급"    char(1),
  "개인사업자여부"            char(1),
  "직장인여부"                char(1),
  "PB고객여부"                char(1),
  "외국인여부"                char(1),
  constraint "TSHDEOA01_pkey" primary key (
    "기준년월",
    "그룹회사코드",
    "그룹고객식별자"
  )
);

comment on table "INST1"."TSHDEOA01" is 'INST1 스키마 · TSHDEOA01 그룹고객 속성';

comment on column "INST1"."TSHDEOA01"."기준년월" is '기준년월 YYYYMM';
comment on column "INST1"."TSHDEOA01"."그룹회사코드" is '금융지주 KFG';
comment on column "INST1"."TSHDEOA01"."그룹고객식별자" is '그룹고객식별자';
comment on column "INST1"."TSHDEOA01"."당월고객계열사수" is '해당 금융기관 고객으로 산정되는 고객 전체 캐피탈사 고객정의 변경으로 (2022.12~2025.05) TSHDE6A01 당월고객여부2 사용';
comment on column "INST1"."TSHDEOA01"."활동고객계열사수" is '[은/증/손/카/푸/캐/생/저] 8개 계열사 중 활동고객인 계열사 수 캐피탈사 고객정의 변경으로 (2022.12~2025.05) TSHDE6A01 활동고객여부2 사용';
comment on column "INST1"."TSHDEOA01"."핵심고객계열사수" is '[은/증/손/카/푸/캐/생/저] 8개 계열사 중 핵심고객인 계열사 수';
comment on column "INST1"."TSHDEOA01"."성별구분" is '고객의 성별 0 : 해당무 1 : 남자 2 : 여자';
comment on column "INST1"."TSHDEOA01"."연령코드" is '고객의 연령으로 10단위로 만 나이기준으로 산출 그룹연령구분코드 001 1세 002 2세 003 3세 004 4세 005 5세 ...... 110 110세이상 999 연령미상';
comment on column "INST1"."TSHDEOA01"."KB스타클럽그룹본인등급" is 'KB스타클럽 그룹등급구분 1: VVIP, 2: VIP, 3: 그랜드, 5: 베스트, 9: 패밀리 (2023년 6월부터 적용) ※ 단, 2023년 5월까지는 1: MVP, 2: 로얄, 3: 골드, 5: 프리미엄, 9: 일반으로 적용';
comment on column "INST1"."TSHDEOA01"."KB스타클럽그룹최고등급" is 'KB스타클럽 그룹등급구분 1: VVIP, 2: VIP, 3: 그랜드, 5: 베스트, 9: 패밀리 (2023년 6월부터 적용) ※ 단, 2023년 5월까지는 1: MVP, 2: 로얄, 3: 골드, 5: 프리미엄, 9: 일반으로 적용';
comment on column "INST1"."TSHDEOA01"."개인사업자여부" is '개인사업자(SOHO)여부 0 : 해당무 1 : 개인사업자';
comment on column "INST1"."TSHDEOA01"."직장인여부" is '직장인 여부 0 : 해당무 1 : 직장인';
comment on column "INST1"."TSHDEOA01"."PB고객여부" is 'PB고객인지 여부 0 : 해당무 1 : PB고객';
comment on column "INST1"."TSHDEOA01"."외국인여부" is '외국인고객인지 여부 0 : 해당무 1 : 외국인';
