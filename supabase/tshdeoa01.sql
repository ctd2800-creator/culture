-- INST1.TSHDEOA01 — 그룹 고객 기본 속성 (메타데이터 명세 기반)
-- Supabase SQL Editor 또는 python supabase/apply_tshdeoa01.py

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

comment on column "INST1"."TSHDEOA01"."기준년월" is '순위1 / PK / CHAR(6) NOT NULL / 속성: 기준년월';
comment on column "INST1"."TSHDEOA01"."그룹회사코드" is '순위2 / PK / CHAR(3) NOT NULL / 속성: 그룹회사코드 / 인스턴스: FG그룹DB그룹회사코드 / 식별자: 0036';
comment on column "INST1"."TSHDEOA01"."그룹고객식별자" is '순위3 / PK / CHAR(10) NOT NULL / 속성: 그룹고객식별자';
comment on column "INST1"."TSHDEOA01"."당월고객계열사수" is '순위4 / NUMBER(3,0) NULLABLE / 속성: 당월고객계열사수';
comment on column "INST1"."TSHDEOA01"."활동고객계열사수" is '순위5 / NUMBER(3,0) NULLABLE / 속성: 활동고객계열사수';
comment on column "INST1"."TSHDEOA01"."핵심고객계열사수" is '순위6 / NUMBER(3,0) NULLABLE / 속성: 핵심고객계열사수';
comment on column "INST1"."TSHDEOA01"."성별구분" is '순위7 / CHAR(1) NULLABLE / 속성: 성별구분코드 / 인스턴스: 성별구분코드 / 식별자: 101644000';
comment on column "INST1"."TSHDEOA01"."연령코드" is '순위8 / CHAR(3) NULLABLE / 속성: 연령코드 / 인스턴스: 연령코드 / 식별자: 116252000';
comment on column "INST1"."TSHDEOA01"."KB스타클럽그룹본인등급" is '순위9 / CHAR(1) NULLABLE / 속성: KB스타클럽그룹본인등급구분코드 / 인스턴스: 고객구분코드 / 식별자: 100243000';
comment on column "INST1"."TSHDEOA01"."KB스타클럽그룹최고등급" is '순위10 / CHAR(1) NULLABLE / 속성: KB스타클럽그룹최고등급구분코드 / 인스턴스: 고객구분코드 / 식별자: 100243000';
comment on column "INST1"."TSHDEOA01"."개인사업자여부" is '순위11 / CHAR(1) NULLABLE / 속성: 개인사업자여부 / 인스턴스: 여부 / 식별자: 102132000';
comment on column "INST1"."TSHDEOA01"."직장인여부" is '순위12 / CHAR(1) NULLABLE / 속성: 직장인여부 / 인스턴스: 여부 / 식별자: 102132000';
comment on column "INST1"."TSHDEOA01"."PB고객여부" is '순위13 / CHAR(1) NULLABLE / 속성: PB고객여부 / 인스턴스: 여부 / 식별자: 102132000';
comment on column "INST1"."TSHDEOA01"."외국인여부" is '순위14 / CHAR(1) NULLABLE / 속성: 외국인여부 / 인스턴스: 여부 / 식별자: 102132000';

-- Dashboard·API에서 INST1 스키마 접근 (이미 있으면 무시)
grant usage on schema "INST1" to postgres, authenticated, service_role, anon;
grant select, insert, update, delete on table "INST1"."TSHDEOA01" to postgres, authenticated, service_role;
grant select on table "INST1"."TSHDEOA01" to anon;
