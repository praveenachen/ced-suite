#!/usr/bin/env python3
"""
Comprehensive ingestion script for both app_library and quant_data collections.
This script can ingest text-rich documents (PDF, TXT, DOCX, MD) from app_library
and quantitative data files (CSV, XLSX) from quant_data directory.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add the parent directory to the Python path so we can import backend modules
script_dir = Path(__file__).parent
project_dir = script_dir.parent
sys.path.insert(0, str(project_dir))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build or update Chroma RAG indexes from local sources."
    )
    parser.add_argument(
        "--library-dir",
        default="backend/app/data/app_library",
        help="Folder containing text-rich documents (PDF, TXT, DOCX, MD).",
    )
    parser.add_argument(
        "--quant-dir",
        default="backend/app/data/quant_data",
        help="Folder containing quantitative data files (CSV, XLSX).",
    )
    parser.add_argument(
        "--persist-dir",
        default=None,
        help="Chroma persistence directory. Defaults to backend/app/data/app_library/vector_store.",
    )
    parser.add_argument(
        "--collection",
        default="grant_library",
        help="App library collection name.",
    )
    parser.add_argument(
        "--quant-collection",
        default="quant_data",
        help="Quantitative data collection name.",
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
        help="Clear existing vectors in both collections before ingesting.",
    )
    parser.add_argument(
        "--app-library-only",
        action="store_true",
        help="Only ingest app_library collection.",
    )
    parser.add_argument(
        "--quant-data-only",
        action="store_true",
        help="Only ingest quant_data collection.",
    )
    parser.add_argument(
        "--ingest-all",
        action="store_true",
        help="Ingest both app_library and quant_data using optimized batch processing.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    from backend.app.rag.ingest import ingest_folder, ingest_quant_data, ingest_all
    from backend.app.rag.store import (
        get_collection,
        get_default_persist_dir,
        get_quant_data_dir,
        get_app_library_dir,
        QUANT_COLLECTION,
        DEFAULT_COLLECTION
    )
    from backend.app.rag.use_cases import collection_for_use_case, normalize_use_case

    library_dir = str(Path(args.library_dir))
    quant_dir = str(Path(args.quant_dir))
    persist_dir = args.persist_dir or get_default_persist_dir()
    use_case = normalize_use_case(args.use_case)

    # Determine collection names based on use case
    app_collection = collection_for_use_case(use_case, base_collection=args.collection)
    quant_collection = collection_for_use_case(use_case, base_collection=args.quant_collection)

    results = {}

    if args.ingest_all:
        print("Starting comprehensive ingestion of both collections...")
        ingest_result = ingest_all(reset=args.reset, persist_dir=persist_dir)

        # Get final collection counts
        app_col = get_collection(persist_dir=persist_dir, collection_name=app_collection)
        quant_col = get_collection(persist_dir=persist_dir, collection_name=quant_collection)

        results = {
            "mode": "ingest_all",
            "app_library_dir": library_dir,
            "quant_data_dir": quant_dir,
            "persist_dir": persist_dir,
            "app_collection": app_collection,
            "quant_collection": quant_collection,
            "use_case": use_case,
            "source_tag": args.source_tag,
            "reset": args.reset,
            "ingest_result": ingest_result,
            "app_collection_count": app_col.count(),
            "quant_collection_count": quant_col.count(),
        }

    elif args.quant_data_only:
        print("Ingesting quantitative data collection...")
        quant_result = ingest_quant_data(
            data_dir=quant_dir,
            persist_dir=persist_dir,
            collection_name=quant_collection,
            reset=args.reset,
        )

        quant_col = get_collection(persist_dir=persist_dir, collection_name=quant_collection)
        results = {
            "mode": "quant_data_only",
            "quant_data_dir": quant_dir,
            "persist_dir": persist_dir,
            "quant_collection": quant_collection,
            "use_case": use_case,
            "reset": args.reset,
            "ingest_result": quant_result,
            "quant_collection_count": quant_col.count(),
        }

    else:
        # Default or app-library-only mode
        print("Ingesting app library collection...")
        app_result = ingest_folder(
            library_dir=library_dir,
            persist_dir=persist_dir,
            collection_name=app_collection,
            reset=args.reset,
            source_tag=args.source_tag,
            use_case=use_case,
        )

        app_col = get_collection(persist_dir=persist_dir, collection_name=app_collection)
        results = {
            "mode": "app_library_only",
            "library_dir": library_dir,
            "persist_dir": persist_dir,
            "app_collection": app_collection,
            "use_case": use_case,
            "source_tag": args.source_tag,
            "reset": args.reset,
            "ingest_result": app_result,
            "app_collection_count": app_col.count(),
        }

    print(f"Ingestion complete! Results: {results}")


if __name__ == "__main__":
    main()