-- 그룹멤버십계열사기초데이터검증 (구 TCHDHC001)
-- Supabase Dashboard → SQL Editor 에서 실행하거나 psycopg로 적용

create table if not exists public."그룹멤버십계열사기초데이터검증" (
  "그룹회사코드"              char(3) not null,
  "기준년월"                char(6) not null,
  "계열사그룹구분"            char(3) not null,
  "계열사등급구분내용"          varchar(2) not null,
  "고객수"                  numeric(11, 0),
  "고객수비율"                numeric(5, 2),
  "고객수증감비율"              numeric(7, 2),
  "합계계열사등급환산점수"        numeric(15, 0),
  "합계계열사등급환산점수증감비율"    numeric(7, 2),
  "합계계열사자체점수"           numeric(15, 0),
  "합계계열사자체점수증감비율"      numeric(7, 2),
  "최소계열사등급환산점수"        numeric(15, 0),
  "최대계열사등급환산점수"        numeric(15, 0),
  "최소계열사자체점수"           numeric(15, 0),
  "최대계열사자체점수"           numeric(15, 0),
  "시스템최초등록일시"           char(20) not null,
  "시스템최종처리일시"           char(20) not null,
  "시스템최종사용자번호"          char(7) not null,
  constraint "그룹멤버십계열사기초데이터검증_pkey" primary key (
    "그룹회사코드",
    "기준년월",
    "계열사그룹구분",
    "계열사등급구분내용"
  )
);

comment on table public."그룹멤버십계열사기초데이터검증" is '계열사 등급·고객수 집계 (구 TCHDHC001)';

comment on column public."그룹멤버십계열사기초데이터검증"."그룹회사코드" is '코드3 / PK';
comment on column public."그룹멤버십계열사기초데이터검증"."기준년월" is '년월6 / PK';
comment on column public."그룹멤버십계열사기초데이터검증"."계열사그룹구분" is '구분코드3 (속성: 계열사그룹구분코드) / PK';
comment on column public."그룹멤버십계열사기초데이터검증"."계열사등급구분내용" is '내용2 / PK';
