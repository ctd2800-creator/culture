-- INST1.TSHDEOA06 — 그룹 신용등급 정보
-- psql 또는 python culture_db/apply_tshdeoa06.py

create schema if not exists "INST1";

create table if not exists "INST1"."TSHDEOA06" (
  "기준년월"              char(6) not null,
  "그룹회사코드"          char(3) not null,
  "그룹고객식별자"        char(10) not null,
  "세그먼트분류명"        varchar(4),
  "실적평점"              numeric(5, 0),
  "일반평점"              numeric(5, 0),
  "결합평점"              numeric(5, 0),
  "통합등급내용"          varchar(2),
  constraint "TSHDEOA06_pkey" primary key (
    "기준년월",
    "그룹회사코드",
    "그룹고객식별자"
  )
);

comment on table "INST1"."TSHDEOA06" is 'INST1 스키마 · TSHDEOA06 그룹신용등급정보';

comment on column "INST1"."TSHDEOA06"."기준년월" is '기준년월';
comment on column "INST1"."TSHDEOA06"."그룹회사코드" is '금융지주 KFG';
comment on column "INST1"."TSHDEOA06"."그룹고객식별자" is '그룹고객식별자 (계열사별 암호화된 고객번호를 그룹에서 그룹고객식별자로 변환작업필요)';
comment on column "INST1"."TSHDEOA06"."세그먼트분류명" is 'SEG1 - 과거 6개월 내 대출보유/SEG2 - 과거 6개월 내 대출 미보유 및 신용카드 보유/SEG3 - 과거 6개월 내 대출 미보유 및 체크카드 보유';
comment on column "INST1"."TSHDEOA06"."실적평점" is '그룹통합 실적모형 평점(지주사 제공)';
comment on column "INST1"."TSHDEOA06"."일반평점" is '그룹통합 일반모형 평점 (KCB 제공)';
comment on column "INST1"."TSHDEOA06"."결합평점" is '그룹통합 소매신용평점 (SEG별 결합가중치 적용)';
comment on column "INST1"."TSHDEOA06"."통합등급내용" is '그룹통합 소매신용등급 (결합평점별 등급구간 적용)';
