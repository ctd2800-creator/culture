-- INST1.TSHDEOA05 — 그룹계열사 마케팅 동의 정보
-- psql 또는 python culture_db/apply_tshdeoa05.py

create schema if not exists "INST1";

create table if not exists "INST1"."TSHDEOA05" (
  "기준년월"                              char(6) not null,
  "정보제공동의계열사구분내용"            varchar(3) not null,
  "그룹고객식별자"                        char(10) not null,
  "계열사마케팅동의여부"                  char(1) not null,
  "계열사마케팅동의년월일"                char(8),
  "계열사마케팅동의종료예정년월일"        char(8),
  constraint "TSHDEOA05_pkey" primary key (
    "기준년월",
    "정보제공동의계열사구분내용",
    "그룹고객식별자"
  )
);

comment on table "INST1"."TSHDEOA05" is 'INST1 스키마 · TSHDEOA05 그룹계열사마케팅정보';

comment on column "INST1"."TSHDEOA05"."기준년월" is '기준년월';
comment on column "INST1"."TSHDEOA05"."정보제공동의계열사구분내용" is '원 그룹계열회사구분값';
comment on column "INST1"."TSHDEOA05"."그룹고객식별자" is '그룹고객식별자 (계열사별 앱으로 회원 고객정보를 그룹에서 그룹고객식별자로 변환작업필요)';
comment on column "INST1"."TSHDEOA05"."계열사마케팅동의여부" is '해당 테이블은 동의한 고객만 적재';
comment on column "INST1"."TSHDEOA05"."계열사마케팅동의년월일" is '계열사마케팅정보제공동의일자';
comment on column "INST1"."TSHDEOA05"."계열사마케팅동의종료예정년월일" is '계열사마케팅정보제공동의 종료 예정일';
