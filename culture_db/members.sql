-- Culture 회원 (로그인 아이디·비밀번호 필수)
-- python culture_db/apply_members

create table if not exists public."회원" (
  "아이디" varchar(50) not null,
  "비밀번호" varchar(255) not null,
  "회원명" varchar(100) not null,
  "이메일" varchar(255),
  "부서명" varchar(100),
  "활성여부" boolean not null default true,
  "가입일시" timestamptz not null default now(),
  constraint "회원_pkey" primary key ("아이디")
);

create index if not exists "회원_이메일_idx" on public."회원" ("이메일");

comment on table public."회원" is 'Culture 앱 회원 (아이디·비밀번호 필수)';
comment on column public."회원"."아이디" is '로그인 ID / PK / NOT NULL';
comment on column public."회원"."비밀번호" is '비밀번호 해시 (werkzeug) / NOT NULL';
