#!/usr/bin/env python3
"""테이블 메타 추출 → 문장화 → Bedrock Embedding → OpenSearch k-NN 적재.

사용 예:
  cd culture
  python scripts/index_schema_metadata.py --export-only
  python scripts/index_schema_metadata.py --recreate-index
  python scripts/index_schema_metadata.py --search "성별별 고객수 집계"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schema_vector.bedrock_embed import embed_texts
from schema_vector.config import (
    metadata_schemas,
    opensearch_index,
    schema_vector_enabled,
)
from schema_vector.metadata_extract import (
    enrich_with_column_definitions,
    enrich_with_instance_ids,
    extract_table_metadata,
)
from schema_vector.sentences import build_schema_documents


def _connect_db():
    from culture_db.culture_db import connect_culture_db

    return connect_culture_db(connect_timeout=30)


def cmd_extract(conn, schemas: list[str], out: Path | None) -> list:
    tables = extract_table_metadata(conn, schemas)
    tables = [
        enrich_with_instance_ids(enrich_with_column_definitions(t)) for t in tables
    ]
    print(f"extracted {len(tables)} tables from schemas {schemas}")
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = [t.to_json() for t in tables]
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote metadata JSON → {out}")
    return tables


def cmd_index(
    tables,
    *,
    export_only: bool,
    export_path: Path,
    recreate: bool,
    skip_embed: bool,
) -> int:
    docs = build_schema_documents(tables)
    print(f"built {len(docs)} documents ({sum(1 for d in docs if d['doc_type']=='table')} tables)")

    texts = [d["text"] for d in docs]
    if skip_embed:
        for d in docs:
            d["embedding"] = []
    else:
        print("embedding via Bedrock Titan...")
        vectors = embed_texts(texts)
        for d, vec in zip(docs, vectors, strict=True):
            d["embedding"] = vec

    export_path.parent.mkdir(parents=True, exist_ok=True)
    with export_path.open("w", encoding="utf-8") as f:
        for d in docs:
            row = {k: v for k, v in d.items() if k != "metadata"}
            row["metadata_json"] = json.dumps(d.get("metadata", {}), ensure_ascii=False)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote export JSONL → {export_path}")

    if export_only or not schema_vector_enabled():
        if export_only:
            print("export-only complete.")
        else:
            print("OPENSEARCH_HOST not set; export only.")
        return 0

    from schema_vector.opensearch_store import bulk_index_documents, ensure_index

    print(f"OpenSearch index: {opensearch_index()}")
    ensure_index(recreate=recreate)
    count, errors = bulk_index_documents(docs)
    if errors:
        print(f"bulk errors ({len(errors)}):", errors[:3], file=sys.stderr)
        return 1
    print(f"indexed {count} documents into {opensearch_index()}")
    return 0


def cmd_search(query: str, k: int) -> int:
    from schema_vector.retriever import get_schema_context_for_query, search_schema

    if not schema_vector_enabled():
        print("OPENSEARCH_HOST 가 설정되어 있지 않습니다.", file=sys.stderr)
        return 1
    hits = search_schema(query, k=k)
    print(get_schema_context_for_query(query, k=k))
    print("---")
    for hit in hits:
        print(
            f"[{hit.get('doc_type')}] {hit.get('doc_id')} "
            f"score={hit.get('score')} :: {hit.get('text', '')[:120]}..."
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Culture 스키마 메타 벡터 적재")
    parser.add_argument(
        "--schemas",
        default=",".join(metadata_schemas()),
        help="쉼표 구분 스키마 (기본: INST1,public)",
    )
    parser.add_argument(
        "--metadata-out",
        type=Path,
        default=ROOT / "exports" / "schema_metadata.json",
        help="추출 메타 JSON 경로",
    )
    parser.add_argument(
        "--export-path",
        type=Path,
        default=ROOT / "exports" / "schema_vectors.jsonl",
        help="문장+임베딩 JSONL 경로",
    )
    parser.add_argument("--export-only", action="store_true", help="OpenSearch 없이 export만")
    parser.add_argument("--recreate-index", action="store_true", help="인덱스 삭제 후 재생성")
    parser.add_argument("--skip-embed", action="store_true", help="임베딩 생략 (테스트용)")
    parser.add_argument("--import-jsonl", action="store_true", help="기존 JSONL만 OpenSearch에 적재")
    parser.add_argument("--search", metavar="QUERY", help="벡터 검색 테스트")
    parser.add_argument("-k", type=int, default=8, help="검색 top-k")
    args = parser.parse_args()

    if args.search:
        return cmd_search(args.search, args.k)

    if args.import_jsonl:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "import_schema_vectors",
            ROOT / "scripts" / "import_schema_vectors.py",
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(mod)
        return mod.run_import(args.export_path, recreate=args.recreate_index)

    schemas = [s.strip() for s in args.schemas.split(",") if s.strip()]
    with _connect_db() as conn:
        tables = cmd_extract(conn, schemas, args.metadata_out)
    return cmd_index(
        tables,
        export_only=args.export_only,
        export_path=args.export_path,
        recreate=args.recreate_index,
        skip_embed=args.skip_embed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
