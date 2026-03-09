from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or update the Chroma RAG index from local .txt sources."
    )
    parser.add_argument(
        "--library-dir",
        default="backend/app/data/app_library",
        help="Folder containing .txt source documents.",
    )
    parser.add_argument(
        "--persist-dir",
        default=None,
        help="Chroma persistence directory. Defaults to backend/app/data/app_library/vector_store.",
    )
    parser.add_argument(
        "--collection",
        default="grant_library",
        help="Chroma collection name.",
    )
    parser.add_argument(
        "--use-case",
        default="default",
        help="Logical use case (e.g., default, fci, municipal).",
    )
    parser.add_argument(
        "--source-tag",
        default=None,
        help="Optional source tag written to metadata (e.g., fci_guidelines_2026).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear existing vectors in the collection before ingesting.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    from backend.app.rag.ingest import ingest_folder
    from backend.app.rag.store import get_collection, get_default_persist_dir
    from backend.app.rag.use_cases import collection_for_use_case, normalize_use_case

    library_dir = str(Path(args.library_dir))
    persist_dir = args.persist_dir or get_default_persist_dir()
    use_case = normalize_use_case(args.use_case)
    collection = collection_for_use_case(use_case, base_collection=args.collection)

    res = ingest_folder(
        library_dir=library_dir,
        persist_dir=persist_dir,
        collection_name=collection,
        reset=args.reset,
        source_tag=args.source_tag,
        use_case=use_case,
    )

    col = get_collection(persist_dir=persist_dir, collection_name=collection)
    print(
        {
            "library_dir": library_dir,
            "persist_dir": persist_dir,
            "collection": collection,
            "use_case": use_case,
            "source_tag": args.source_tag,
            "reset": args.reset,
            "ingest_result": res,
            "collection_count": col.count(),
        }
    )


if __name__ == "__main__":
    main()
