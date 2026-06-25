# Culture

Aurora PostgreSQL 테이블 데이터를 LangGraph로 조회·요약하고 Bedrock(Claude Sonnet 4.5)으로 응답하는 Flask 앱.

## 프로젝트 구조

```
culture/
├── culture_app.py          # Flask 앱 (채팅 UI, API)
├── culture_workflow.py     # LangGraph: Fetch → Summarize → Reply
├── static/culture_chat.js
├── api/index.py            # Vercel serverless 엔트리
├── supabase/               # DDL, 시드, IAM 예시 (회원 테이블 포함)
├── requirements.txt
├── vercel.json
├── pyproject.toml
├── run_culture.bat
└── .env.local.example
```

## 로컬 실행

```bash
cd culture
pip install -r requirements.txt
copy .env.local.example .env.local   # 값 입력
python culture_app.py
```

또는 `run_culture.bat` 실행 → http://127.0.0.1:5051

처음 접속 시 **로그인 화면**(`/login`)으로 이동합니다. 로그인 성공 후 AI 채팅 화면에서 회원명·부서·이메일이 표시됩니다.

### 회원 테이블 (`회원`)

로컬 앱 기동 시 `AURORA_DB_URL` 이 있으면 테이블 생성·10명 시드(비어 있을 때만)를 시도합니다.  
수동 적용:

```bash
cd culture
python supabase/apply_members.py          # DDL + 10명 등록
python supabase/apply_members.py --force-seed   # 기존 행도 upsert
```

| 컬럼 | 설명 |
|------|------|
| `아이디` | 로그인 ID (PK, NOT NULL) |
| `비밀번호` | 비밀번호 해시 (NOT NULL) |
| `회원명` | 이름 |
| `이메일` / `부서명` | 선택 정보 |

시드 계정 예: `culture01` / `Pass01!culture` … `culture10` / `Pass10!culture`

### INST1.TSHDEOA01 테이블

그룹 고객 속성 테이블 (스키마 `INST1`, 테이블 `TSHDEOA01`, PK: 기준년월·그룹회사코드·그룹고객식별자).

```bash
cd culture
python supabase/apply_tshdeoa01.py
```

### INST1.TSHDEOA02 테이블

그룹 고객 거래·잔액·상품 요약 (18컬럼, PK: 기준년월·그룹회사코드·그룹고객식별자).

```bash
cd culture
python supabase/apply_tshdeoa02.py
```

### INST1.TSHDE0ZCD 테이블

인스턴스 코드 마스터 (9컬럼, PK: 그룹회사코드·인스턴스식별자·인스턴스코드·유효시작년월일).

```bash
cd culture
python supabase/apply_tshde0zcd.py
```

## 환경 변수

| 변수 | 설명 |
|------|------|
| `AURORA_DB_URL` | Aurora Postgres 연결 문자열 |
| `FLASK_SECRET_KEY` | 세션 키 |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Bedrock |
| `AWS_SESSION_TOKEN` 또는 `AWS_SECURITY_TOKEN` | 임시 자격 증명 시 |
| `AWS_REGION` | 예: `ap-northeast-2` |
| `BEDROCK_MODEL_ID` | (선택) 기본 `anthropic.claude-sonnet-4-5-20250929-v1:0` |

## Vercel 배포

1. GitHub 저장소 연결
2. **Root Directory** → `culture` (저장소 루트가 상위 폴더인 경우)
3. 환경 변수 설정 후 Deploy

프로덕션: https://culture-seong-youn-choi-s-projects.vercel.app
