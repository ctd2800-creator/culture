-- INST1.TSHDE0ZCD — 인스턴스 코드 마스터
-- Supabase SQL Editor 또는 python supabase/apply_tshde0zcd.py

create schema if not exists "INST1";

create table if not exists "INST1"."TSHDE0ZCD" (
  "그룹회사코드"        char(3) not null,
  "인스턴스식별자"      char(9) not null,
  "인스턴스코드"        char(14) not null,
  "유효시작년월일"      char(8) not null,
  "유효종료년월일"      char(8),
  "인스턴스명"          varchar(80),
  "인스턴스내용"        varchar(250),
  "그룹최초등록일시"    timestamp,
  "그룹최종변경일시"    timestamp,
  constraint "TSHDE0ZCD_pkey" primary key (
    "그룹회사코드",
    "인스턴스식별자",
    "인스턴스코드",
    "유효시작년월일"
  )
);

comment on table "INST1"."TSHDE0ZCD" is 'INST1 스키마 · TSHDE0ZCD 인스턴스 코드';

comment on column "INST1"."TSHDE0ZCD"."그룹회사코드" is '순위1 / PK / CHAR(3) NOT NULL / 속성: 그룹회사코드 / 인스턴스: FG그룹DB그룹회사코드 / 식별자: 0036';
comment on column "INST1"."TSHDE0ZCD"."인스턴스식별자" is '순위2 / PK / CHAR(9) NOT NULL / 속성: 인스턴스식별자';
comment on column "INST1"."TSHDE0ZCD"."인스턴스코드" is '순위3 / PK / CHAR(14) NOT NULL / 속성: 인스턴스코드 / 인스턴스: 인스턴스코드 / 식별자: 111891000';
comment on column "INST1"."TSHDE0ZCD"."유효시작년월일" is '순위4 / PK / CHAR(8) NOT NULL / 속성: 유효시작년월일';
comment on column "INST1"."TSHDE0ZCD"."유효종료년월일" is '순위5 / CHAR(8) NULLABLE / 속성: 유효종료년월일';
comment on column "INST1"."TSHDE0ZCD"."인스턴스명" is '순위6 / VARCHAR(80) NULLABLE / 속성: 인스턴스명';
comment on column "INST1"."TSHDE0ZCD"."인스턴스내용" is '순위7 / VARCHAR(250) NULLABLE / 속성: 인스턴스내용';
comment on column "INST1"."TSHDE0ZCD"."그룹최초등록일시" is '순위8 / TIMESTAMP NULLABLE / 속성: 그룹최초등록일시';
comment on column "INST1"."TSHDE0ZCD"."그룹최종변경일시" is '순위9 / TIMESTAMP NULLABLE / 속성: 그룹최종변경일시';

grant usage on schema "INST1" to postgres, authenticated, service_role, anon;
grant select, insert, update, delete on table "INST1"."TSHDE0ZCD" to postgres, authenticated, service_role;
grant select on table "INST1"."TSHDE0ZCD" to anon;
