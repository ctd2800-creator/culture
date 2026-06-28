-- INST1.TSHDEOA04 — 그룹 고객 소득·급여·대출 요약
-- psql 또는 python culture_db/apply_tshdeoa04.py

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

comment on column "INST1"."TSHDEOA04"."기준년월" is '기준년월 YYYYMM';
comment on column "INST1"."TSHDEOA04"."그룹회사코드" is '금융지주 KFG';
comment on column "INST1"."TSHDEOA04"."그룹고객식별자" is '그룹고객식별자';
comment on column "INST1"."TSHDEOA04"."그룹직업분류코드" is '그룹직업구분에 따른 고객의 직업, 그룹직업구분코드 (별도생성)';
comment on column "INST1"."TSHDEOA04"."급여이체여부" is '고객의 급여이체 고객여부';
comment on column "INST1"."TSHDEOA04"."급여이체금액" is '고객의 기준월 급여이체금액';
comment on column "INST1"."TSHDEOA04"."최근3개월급여이체평균금액" is '고객의 최근3개월 급여이체평균금액';
comment on column "INST1"."TSHDEOA04"."연소득금액" is '고객의 연소득금액';
comment on column "INST1"."TSHDEOA04"."연본인근로소득" is '고객의 연본인근로소득';
comment on column "INST1"."TSHDEOA04"."연본인사업소득" is '고객의 연본인사업소득';
comment on column "INST1"."TSHDEOA04"."그룹총대출잔액" is '고객의 여신계약금액 합산';
comment on column "INST1"."TSHDEOA04"."그룹연체잔액" is '고객의 연체잔액 합산';
comment on column "INST1"."TSHDEOA04"."그룹최대연체일수" is '고객의 최장연체일수';
