# Culture

Supabase 테이블 데이터를 LangGraph로 조회·요약하고 Bedrock(Claude Sonnet 4.5)으로 응답하는 Flask 앱.

## 프로젝트 구조

```
culture/
├── culture_app.py          # Flask 앱 (채팅 UI, API)
├── culture_workflow.py     # LangGraph: Fetch → Summarize → Reply
├── static/culture_chat.js
├── api/index.py            # Vercel serverless 엔트리
├── supabase/               # DDL, 시드, IAM 예시
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

## 환경 변수

| 변수 | 설명 |
|------|------|
| `SUPABASE_DB_URL` | Postgres 연결 문자열 |
| `FLASK_SECRET_KEY` | 세션 키 |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Bedrock |
| `AWS_SESSION_TOKEN` 또는 `AWS_SECURITY_TOKEN` | 임시 자격 증명 시 |
| `AWS_REGION` | 예: `ap-northeast-2` |
| `BEDROCK_MODEL_ID` | (선택) 기본 `anthropic.claude-sonnet-4-5-20250929-v1:0` |

## Vercel 배포

1. GitHub 저장소 연결
2. **Root Directory** → `culture` (저장소 루트가 상위 폴더인 경우)
3. 환경 변수 설정 후 Deploy

프로덕션: https://keebee-seven.vercel.app
