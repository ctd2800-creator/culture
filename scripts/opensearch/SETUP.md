# OpenSearch 도메인 준비 (Culture 스키마 벡터)

서울 리전(`ap-northeast-2`) · 도메인명 `culture-schema` · 퍼블릭 엔드포인트 + IAM

## 1. IAM 정책 (관리자 1회)

현재 `Seungyoon-Choi` 사용자는 `es:*` / `iam:AttachUserPolicy` 권한이 없습니다.  
**계정 관리자**가 아래 JSON을 IAM에 등록·연결해야 합니다.

| 파일 | 용도 |
|------|------|
| `iam-culture-opensearch-manage.json` | 도메인 생성·설정 + HTTP API |
| `iam-culture-opensearch-data.json` | HTTP API만 (운영·Vercel용 IAM 사용자) |

### 콘솔

1. IAM → 정책 → **정책 생성** → JSON 붙여넣기
2. IAM → 사용자 `Seungyoon-Choi` → 권한 추가 → 위 정책 연결

### CLI (관리자)

```powershell
cd culture
.\scripts\opensearch\attach_iam_policy.ps1
```

## 2. 도메인 생성

```powershell
.\scripts\opensearch\create_domain.ps1
```

- 엔진: OpenSearch 2.11
- 인스턴스: `t3.small.search` × 1 (개발용)
- 퍼블릭 엔드포인트 (VPC 미사용 — 로컬/Vercel에서 IAM 서명 접속)
- 액세스 정책: `domain-access-policy.json` (IAM 사용자 + root)

완료 후 출력되는 호스트를 `.env.local`에 추가:

```env
OPENSEARCH_HOST=search-culture-schema-xxxxx.ap-northeast-2.es.amazonaws.com
OPENSEARCH_INDEX=culture-schema-meta
OPENSEARCH_REGION=ap-northeast-2
OPENSEARCH_USE_IAM=1
```

## 3. 메타 벡터 적재

```powershell
cd culture

# (1) Aurora에서 추출 + Bedrock 임베딩 + OpenSearch 적재 (한 번에)
python scripts/index_schema_metadata.py --recreate-index

# (2) 이미 만든 JSONL만 bulk import
python scripts/import_schema_vectors.py --recreate-index

# (3) 검색 테스트
python scripts/index_schema_metadata.py --search "성별별 고객수 집계"
```

## 4. Vercel 연동 (선택)

1. Vercel용 IAM 사용자 또는 Bedrock과 동일 Access Key 사용
2. `domain-access-policy.json`의 `Principal.AWS`에 해당 ARN 추가
3. Vercel 환경 변수에 `OPENSEARCH_HOST`, `OPENSEARCH_USE_IAM=1` 설정

## 5. 비용·보안 참고

- `t3.small.search` + 20GB gp3: 소규모 메타(~200문서)에 충분
- 도메인 삭제: `aws opensearch delete-domain --domain-name culture-schema`
- Aurora와 **동일 VPC 불필요** (메타만 OpenSearch, 데이터는 Aurora)

## 파일 목록

```
scripts/opensearch/
  iam-culture-opensearch-manage.json
  iam-culture-opensearch-data.json
  domain-access-policy.json
  attach_iam_policy.ps1
  create_domain.ps1
  SETUP.md
scripts/import_schema_vectors.py
```
