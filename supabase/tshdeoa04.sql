-- INST1.TSHDEOA04 — 그룹 고객 소득·급여·대출 요약
-- Supabase SQL Editor 또는 python supabase/apply_tshdeoa04.py

create schema if not exists "INST1";

create table if not exists "INST1"."TSHDEOA04" (
  "기준년월"                      char(6) not null,
  "그룹회사코드"                  char(3) not null,
  "그룹고객식별자"                char(10) not null,
  "그룹직업분류코드"              char(1),
  "급여이체여부"                  char(1),
  "급여이체금액"                  numeric(15, 0),
  "최근3개월급여이체평균금액"     numeric(15, 0),
  "연소득금액"                    numeric(15, 0),
  "연본인근로소득"                numeric(15, 0),
  "연본인사업소득"                numeric(15, 0),
  "그룹총대출잔액"                numeric(15, 0),
  "그룹연체잔액"                  numeric(15, 0),
  "그룹최대연체일수"              numeric(5, 0),
  constraint "TSHDEOA04_pkey" primary key (
    "기준년월",
    "그룹회사코드",
    "그룹고객식별자"
  )
);

comment on table "INST1"."TSHDEOA04" is 'INST1 스키마 · TSHDEOA04 그룹고객 소득·대출';

comment on column "INST1"."TSHDEOA04"."기준년월" is '순위1 / PK / CHAR(6) NOT NULL / 속성: 기준년월';
comment on column "INST1"."TSHDEOA04"."그룹회사코드" is '순위2 / PK / CHAR(3) NOT NULL / 속성: 그룹회사코드 / 인스턴스: FG그룹DB그룹회사코드 / 식별자: 0036';
comment on column "INST1"."TSHDEOA04"."그룹고객식별자" is '순위3 / PK / CHAR(10) NOT NULL / 속성: 그룹고객식별자';
comment on column "INST1"."TSHDEOA04"."그룹직업분류코드" is '순위4 / CHAR(1) NULLABLE / 속성: 그룹직업분류코드 / 인스턴스: FG그룹직업분류코드 / 식별자: 132648000';
comment on column "INST1"."TSHDEOA04"."급여이체여부" is '순위5 / CHAR(1) NULLABLE / 속성: 급여이체여부 / 인스턴스: 여부 / 식별자: 102132000';
comment on column "INST1"."TSHDEOA04"."급여이체금액" is '순위6 / NUMBER(15,0) NULLABLE / 속성: 급여이체금액';
comment on column "INST1"."TSHDEOA04"."최근3개월급여이체평균금액" is '순위7 / NUMBER(15,0) NULLABLE / 속성: 최근3개월급여이체평균금액';
comment on column "INST1"."TSHDEOA04"."연소득금액" is '순위8 / NUMBER(15,0) NULLABLE / 속성: 연소득금액';
comment on column "INST1"."TSHDEOA04"."연본인근로소득" is '순위9 / NUMBER(15,0) NULLABLE / 속성: 연본인근로소득';
comment on column "INST1"."TSHDEOA04"."연본인사업소득" is '순위10 / NUMBER(15,0) NULLABLE / 속성: 연본인사업소득';
comment on column "INST1"."TSHDEOA04"."그룹총대출잔액" is '순위11 / NUMBER(15,0) NULLABLE / 속성: 그룹총대출잔액';
comment on column "INST1"."TSHDEOA04"."그룹연체잔액" is '순위12 / NUMBER(15,0) NULLABLE / 속성: 그룹연체잔액';
comment on column "INST1"."TSHDEOA04"."그룹최대연체일수" is '순위13 / NUMBER(5,0) NULLABLE / 속성: 그룹최대연체일수';

grant usage on schema "INST1" to postgres, authenticated, service_role, anon;
grant select, insert, update, delete on table "INST1"."TSHDEOA04" to postgres, authenticated, service_role;
grant select on table "INST1"."TSHDEOA04" to anon;
