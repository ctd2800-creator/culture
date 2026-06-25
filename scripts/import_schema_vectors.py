#!/usr/bin/env python3
"""exports/schema_vectors.jsonl → OpenSearch bulk import (임베딩 재계산 없음)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schema_vector.config import opensearch_index, schema_vector_enabled
from schema_vector.opensearch_store import bulk_index_documents, ensure_index


def load_jsonl(path: Path) -> list[dict]:
    docs: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            embedding = row.get("embedding") or []
            if not embedding:
                raise ValueError(f"line {line_no}: embedding missing (re-run index with Bedrock)")
            meta_raw = row.get("metadata_json") or "{}"
            try:
                metadata = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
            except json.JSONDecodeError:
                metadata = {}
            docs.append(
                {
                    "doc_id": row["doc_id"],
                    "doc_type": row.get("doc_type", ""),
                    "schema": row.get("schema", ""),
                    "table": row.get("table", ""),
                    "column": row.get("column", ""),
                    "table_korean": row.get("table_korean", ""),
                    "text": row.get("text", ""),
                    "metadata": metadata,
                    "embedding": embedding,
                }
            )
    return docs


def run_import(path: Path, *, recreate: bool = False, batch_size: int = 50) -> int:
    if not schema_vector_enabled():
        print("Set OPENSEARCH_HOST in .env.local first.", file=sys.stderr)
        return 1
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        print("Run: python scripts/index_schema_metadata.py --export-only", file=sys.stderr)
        return 1

    docs = load_jsonl(path)
    print(f"loaded {len(docs)} documents from {path}")
    ensure_index(recreate=recreate)
    print(f"index: {opensearch_index()}")

    total = 0
    errors: list[str] = []
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        count, batch_errors = bulk_index_documents(batch, refresh=False)
        total += count
        errors.extend(batch_errors)
        print(f"  indexed {min(i + batch_size, len(docs))}/{len(docs)}")

    if errors:
        print(f"errors ({len(errors)}):", errors[:5], file=sys.stderr)
        return 1
    print(f"OK: imported {total} documents")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="JSONL bulk import to OpenSearch")
    parser.add_argument(
        "--path",
        type=Path,
        default=ROOT / "exports" / "schema_vectors.jsonl",
        help="schema_vectors.jsonl path",
    )
    parser.add_argument("--recreate-index", action="store_true")
    parser.add_argument("--batch-size", type=int, default=50)
    args = parser.parse_args()
    return run_import(args.path, recreate=args.recreate_index, batch_size=args.batch_size)


if __name__ == "__main__":
    raise SystemExit(main())
