-- INST1.TSHDEOA02 — 그룹 고객 거래·잔액·상품 요약
-- psql 또는 python culture_db/apply_tshdeoa02.py

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

comment on column "INST1"."TSHDEOA02"."기준년월" is '기준년월 YYYYMM';
comment on column "INST1"."TSHDEOA02"."그룹회사코드" is '금융지주 "KFG"';
comment on column "INST1"."TSHDEOA02"."그룹고객식별자" is '그룹기준 고객에게 부여되는 고객의 식별자';
comment on column "INST1"."TSHDEOA02"."그룹최초거래년월일" is 'CIF(고객정보) 최초등록일 또는 최초계좌신규일';
comment on column "INST1"."TSHDEOA02"."그룹최근거래년월일" is '고객이 보유한 계좌의 최종거래일';
comment on column "INST1"."TSHDEOA02"."거래기간구분" is '고객이 KB금융그룹과 거래한 기간구분 그룹거래기간구분코드 00 해당무 01 01개월이하 02 02개월이하 ... 12 12개월이하 13 01년이상 14 05년이상 15 10년이상 16 15년이상 17 20년이상';
comment on column "INST1"."TSHDEOA02"."창구거래건수" is '고객의 기준월 창구거래건수';
comment on column "INST1"."TSHDEOA02"."비대면거래건수" is '고객의 기준월 비대면거래건수';
comment on column "INST1"."TSHDEOA02"."최근5년최고수신잔액" is '최근 5년내 월별 수신잔액중 최고금액';
comment on column "INST1"."TSHDEOA02"."최근5년최고여신잔액" is '최근 5년내 월별 여신잔액중 최고금액';
comment on column "INST1"."TSHDEOA02"."수신잔액" is '기준월말 수신잔액';
comment on column "INST1"."TSHDEOA02"."여신잔액" is '기준월말 여신잔액';
comment on column "INST1"."TSHDEOA02"."보유수신상품계약수" is '기준월말 정상 수신계좌수';
comment on column "INST1"."TSHDEOA02"."보유여신상품계약수" is '기준월말 정상 여신계좌수';
comment on column "INST1"."TSHDEOA02"."당월상품신규계약수" is '기준월 신규상품 계좌수';
comment on column "INST1"."TSHDEOA02"."당월상품해지계약수" is '기준월 해지상품 계좌수';
comment on column "INST1"."TSHDEOA02"."급여이체여부" is '고객의 기준월 급여이체여부';
comment on column "INST1"."TSHDEOA02"."연금이체여부" is '고객의 기준월 연금(국민연금, 군인연금, 사학연금, 공무원연금) 이체여부';
