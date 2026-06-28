-- Culture 로그인 사용자 질문 내역
-- python culture_db/apply_question_log.py

create table if not exists public."질문내역" (
  "일련번호" bigint generated always as identity,
  "아이디" varchar(50) not null,
  "질문내용" text not null,
  "등록일시" timestamptz not null default now(),
  constraint "질문내역_pkey" primary key ("일련번호")
);

create index if not exists "질문내역_아이디_등록일시_idx"
  on public."질문내역" ("아이디", "등록일시" desc);

comment on table public."질문내역" is 'Culture 앱 로그인 사용자 질문 내역';
comment on column public."질문내역"."일련번호" is '질문 일련번호 / PK / 자동증가';
comment on column public."질문내역"."아이디" is '질문한 회원 로그인 ID / NOT NULL';
comment on column public."질문내역"."질문내용" is '사용자가 입력한 질문 원문 / NOT NULL';
comment on column public."질문내역"."등록일시" is '질문 등록 시각 / 기본값 now()';
