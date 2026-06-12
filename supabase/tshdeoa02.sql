-- INST1.TSHDEOA02 — 그룹 고객 거래·잔액·상품 요약
-- Supabase SQL Editor 또는 python supabase/apply_tshdeoa02.py

create schema if not exists "INST1";

create table if not exists "INST1"."TSHDEOA02" (
  "기준년월"                  char(6) not null,
  "그룹회사코드"              char(3) not null,
  "그룹고객식별자"            char(10) not null,
  "그룹최초거래년월일"        char(8),
  "그룹최근거래년월일"        char(8),
  "거래기간구분"              char(2),
  "창구거래건수"              numeric(9, 0),
  "비대면거래건수"            numeric(9, 0),
  "최근5년최고수신잔액"       numeric(15, 0),
  "최근5년최고여신잔액"       numeric(15, 0),
  "수신잔액"                  numeric(15, 0),
  "여신잔액"                  numeric(15, 0),
  "보유수신상품계약수"        numeric(9, 0),
  "보유여신상품계약수"        numeric(9, 0),
  "당월상품신규계약수"        numeric(9, 0),
  "당월상품해지계약수"        numeric(9, 0),
  "급여이체여부"              char(1),
  "연금이체여부"              char(1),
  constraint "TSHDEOA02_pkey" primary key (
    "기준년월",
    "그룹회사코드",
    "그룹고객식별자"
  )
);

comment on table "INST1"."TSHDEOA02" is 'INST1 스키마 · TSHDEOA02 그룹고객 거래·잔액·상품';

comment on column "INST1"."TSHDEOA02"."기준년월" is '순위1 / PK / CHAR(6) NOT NULL / 속성: 기준년월';
comment on column "INST1"."TSHDEOA02"."그룹회사코드" is '순위2 / PK / CHAR(3) NOT NULL / 속성: 그룹회사코드';
comment on column "INST1"."TSHDEOA02"."그룹고객식별자" is '순위3 / PK / CHAR(10) NOT NULL / 속성: 그룹고객식별자';
comment on column "INST1"."TSHDEOA02"."그룹최초거래년월일" is '순위4 / CHAR(8) NULLABLE / 속성: 그룹최초거래년월일';
comment on column "INST1"."TSHDEOA02"."그룹최근거래년월일" is '순위5 / CHAR(8) NULLABLE / 속성: 그룹최근거래년월일';
comment on column "INST1"."TSHDEOA02"."거래기간구분" is '순위6 / CHAR(2) NULLABLE / 속성: 거래기간구분코드';
comment on column "INST1"."TSHDEOA02"."창구거래건수" is '순위7 / NUMBER(9,0) NULLABLE / 속성: 창구거래건수';
comment on column "INST1"."TSHDEOA02"."비대면거래건수" is '순위8 / NUMBER(9,0) NULLABLE / 속성: 비대면거래건수';
comment on column "INST1"."TSHDEOA02"."최근5년최고수신잔액" is '순위9 / NUMBER(15,0) NULLABLE / 속성: 최근5년최고수신잔액';
comment on column "INST1"."TSHDEOA02"."최근5년최고여신잔액" is '순위10 / NUMBER(15,0) NULLABLE / 속성: 최근5년최고여신잔액';
comment on column "INST1"."TSHDEOA02"."수신잔액" is '순위11 / NUMBER(15,0) NULLABLE / 속성: 수신잔액';
comment on column "INST1"."TSHDEOA02"."여신잔액" is '순위12 / NUMBER(15,0) NULLABLE / 속성: 여신잔액';
comment on column "INST1"."TSHDEOA02"."보유수신상품계약수" is '순위13 / NUMBER(9,0) NULLABLE / 속성: 보유수신상품계약수';
comment on column "INST1"."TSHDEOA02"."보유여신상품계약수" is '순위14 / NUMBER(9,0) NULLABLE / 속성: 보유여신상품계약수';
comment on column "INST1"."TSHDEOA02"."당월상품신규계약수" is '순위15 / NUMBER(9,0) NULLABLE / 속성: 당월상품신규계약수';
comment on column "INST1"."TSHDEOA02"."당월상품해지계약수" is '순위16 / NUMBER(9,0) NULLABLE / 속성: 당월상품해지계약수';
comment on column "INST1"."TSHDEOA02"."급여이체여부" is '순위17 / CHAR(1) NULLABLE / 속성: 급여이체여부';
comment on column "INST1"."TSHDEOA02"."연금이체여부" is '순위18 / CHAR(1) NULLABLE / 속성: 연금이체여부';

grant usage on schema "INST1" to postgres, authenticated, service_role, anon;
grant select, insert, update, delete on table "INST1"."TSHDEOA02" to postgres, authenticated, service_role;
grant select on table "INST1"."TSHDEOA02" to anon;
