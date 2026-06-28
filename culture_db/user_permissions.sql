-- Culture 사용자별 테이블 접근 권한
-- python culture_db/apply_user_permissions.py

create table if not exists public."유저권한" (
  "아이디" varchar(50) not null,
  "테이블코드" varchar(50) not null,
  "등록일시" timestamptz not null default now(),
  constraint "유저권한_pkey" primary key ("아이디", "테이블코드")
);

create index if not exists "유저권한_아이디_idx"
  on public."유저권한" ("아이디");

comment on table public."유저권한" is 'Culture 앱 사용자별 접근 가능한 테이블 목록';
comment on column public."유저권한"."아이디" is '회원 로그인 ID / NOT NULL';
comment on column public."유저권한"."테이블코드" is '접근 가능한 INST1 테이블 코드 (예: TSHDEOA01) / NOT NULL';
comment on column public."유저권한"."등록일시" is '권한 등록 시각 / 기본값 now()';
