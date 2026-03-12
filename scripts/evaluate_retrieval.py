"""
Retrieval Accuracy Evaluation Script
=====================================
Measures retrieval quality of the RAG pipeline against a curated set of
queries with known relevant documents.

Metrics:
  - Precision@K: fraction of retrieved docs that are relevant
  - Recall@K:    fraction of relevant docs that are retrieved
  - MRR:         Mean Reciprocal Rank (rank of first relevant result)
  - nDCG@K:      Normalized Discounted Cumulative Gain

Usage:
  # Live evaluation (requires OPENAI_API_KEY):
  python scripts/evaluate_retrieval.py

  # Mocked evaluation (no API key needed):
  python scripts/evaluate_retrieval.py --mock

  # Use hybrid search:
  python scripts/evaluate_retrieval.py --mode hybrid

  # Adjust K parameter:
  python scripts/evaluate_retrieval.py --k 10
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ──────────────────────────────────────────────
# Evaluation Queries
# ──────────────────────────────────────────────
# Each query has:
#   - query: the search string
#   - relevant_keywords: keywords that MUST appear in a relevant chunk
#   - relevant_sources: filename substrings that count as relevant
#   - description: human-readable purpose of the query
EVAL_QUERIES = [
    {
        "query": "affordable housing infrastructure funding",
        "description": "Should retrieve housing-related proposals and funding guides",
        "relevant_keywords": ["housing", "infrastructure", "fund"],
        "relevant_sources": [
            "CMHC", "Housing", "housing", "Build Now", "Full-Proposal",
            "Municipal Data",
        ],
    },
    {
        "query": "SSHRC Insight Development Grant application requirements",
        "description": "Should retrieve SSHRC proposal and program guide content",
        "relevant_keywords": ["sshrc", "insight", "grant"],
        "relevant_sources": [
            "SSHRC", "sshrc",
        ],
    },
    {
        "query": "community economic development Nunavut northern Canada",
        "description": "Should retrieve CanNor, community-focused proposals",
        "relevant_keywords": ["community", "economic", "development", "nunavut", "northern"],
        "relevant_sources": [
            "CanNor", "CED", "ced", "community",
        ],
    },
    {
        "query": "budget justification and allocation for grant proposals",
        "description": "Should retrieve budget templates and proposal guides",
        "relevant_keywords": ["budget", "justification", "allocation"],
        "relevant_sources": [
            "template", "Template", "guide", "Budget", "budget",
        ],
    },
    {
        "query": "machine learning artificial intelligence research",
        "description": "Should retrieve AI/ML-related proposals",
        "relevant_keywords": ["machine learning", "artificial intelligence", "ai", "ml"],
        "relevant_sources": [
            "AI", "ai", "GS AI", "MITACS",
        ],
    },
    {
        "query": "water quality boil water advisory pipes repair cost",
        "description": "Should retrieve quantitative data about water infrastructure",
        "relevant_keywords": ["water", "boil", "advisory", "pipe", "repair"],
        "relevant_sources": [
            "water", "Water",
        ],
    },
    {
        "query": "population demographics housing vacancy rate statistics",
        "description": "Should retrieve quantitative community statistics",
        "relevant_keywords": ["population", "vacancy", "rate", "statistic"],
        "relevant_sources": [
            "stats", "census", "population", "housing",
        ],
    },
    {
        "query": "MITACS internship application partnership industry",
        "description": "Should retrieve MITACS proposals",
        "relevant_keywords": ["mitacs", "internship", "partner"],
        "relevant_sources": [
            "MITACS", "mitacs", "Mitacs",
        ],
    },
    {
        "query": "evaluation criteria scoring rubric grant review",
        "description": "Should retrieve scorecards and rubrics",
        "relevant_keywords": ["evaluat", "criteria", "scor", "rubric", "review"],
        "relevant_sources": [
            "scorecard", "Scorecard", "rubric", "Rubric", "evaluation",
        ],
    },
    {
        "query": "letter of intent proposal concept paper submission",
        "description": "Should retrieve LOI, concept papers, and submission guides",
        "relevant_keywords": ["letter of intent", "loi", "concept paper", "submission"],
        "relevant_sources": [
            "LOI", "loi", "Concept", "concept", "Capstone", "EOI",
        ],
    },
]


# ──────────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────────
def is_relevant(result: Dict[str, Any], query_spec: Dict) -> bool:
    """Check if a retrieved result is relevant based on keyword and source matching."""
    text = (result.get("document") or "").lower()
    source = (result.get("source") or "").lower()

    # Check keyword match
    keyword_match = any(
        kw.lower() in text for kw in query_spec["relevant_keywords"]
    )
    # Check source match
    source_match = any(
        s.lower() in source for s in query_spec["relevant_sources"]
    )

    return keyword_match or source_match


def precision_at_k(results: List[Dict], query_spec: Dict, k: int) -> float:
    """Fraction of top-K results that are relevant."""
    top_k = results[:k]
    if not top_k:
        return 0.0
    relevant = sum(1 for r in top_k if is_relevant(r, query_spec))
    return relevant / len(top_k)


def recall_at_k(results: List[Dict], query_spec: Dict, k: int, total_relevant_est: int = 5) -> float:
    """Fraction of relevant docs found in top-K (approximate)."""
    top_k = results[:k]
    relevant = sum(1 for r in top_k if is_relevant(r, query_spec))
    return relevant / total_relevant_est if total_relevant_est > 0 else 0.0


def mean_reciprocal_rank(results: List[Dict], query_spec: Dict) -> float:
    """1/rank of the first relevant result."""
    for i, r in enumerate(results, start=1):
        if is_relevant(r, query_spec):
            return 1.0 / i
    return 0.0


def ndcg_at_k(results: List[Dict], query_spec: Dict, k: int) -> float:
    """Normalized Discounted Cumulative Gain at K."""
    top_k = results[:k]
    dcg = 0.0
    for i, r in enumerate(top_k, start=1):
        rel = 1.0 if is_relevant(r, query_spec) else 0.0
        dcg += rel / math.log2(i + 1)

    # Ideal DCG: all relevant docs first
    num_rel = sum(1 for r in top_k if is_relevant(r, query_spec))
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, num_rel + 1))

    return dcg / idcg if idcg > 0 else 0.0


# ──────────────────────────────────────────────
# Evaluation Runner
# ──────────────────────────────────────────────
def run_evaluation(
    mode: str = "hybrid",
    k: int = 6,
    persist_dir: Optional[str] = None,
    collection_name: str = "grant_library",
    use_mock: bool = False,
) -> Dict[str, Any]:
    """
    Run the full evaluation suite.
    
    Args:
        mode: "dense", "sparse", or "hybrid"
        k: Top-K for metrics
        persist_dir: Vector store directory
        collection_name: ChromaDB collection name
        use_mock: If True, use mocked embeddings (no API key needed)
    """
    from backend.app.rag.retrieve import (
        dense_retrieve, sparse_retrieve, hybrid_retrieve, retrieve_detailed
    )

    query_results = []

    for i, q in enumerate(EVAL_QUERIES, 1):
        print(f"\n  [{i}/{len(EVAL_QUERIES)}] {q['description']}")
        print(f"    Query: \"{q['query']}\"")

        try:
            if mode == "dense":
                raw_results = dense_retrieve(
                    q["query"], top_k=k * 2,
                    persist_dir=persist_dir, collection_name=collection_name
                )
            elif mode == "sparse":
                raw_results = sparse_retrieve(
                    q["query"], top_k=k * 2,
                    collection_name=collection_name
                )
            elif mode == "hybrid":
                raw_results = hybrid_retrieve(
                    q["query"], top_k=k * 2,
                    persist_dir=persist_dir, collection_name=collection_name
                )
            else:
                raw_results = hybrid_retrieve(
                    q["query"], top_k=k * 2,
                    persist_dir=persist_dir, collection_name=collection_name
                )

            # Normalize results to dicts
            results = []
            for doc_id, doc, meta, score in raw_results:
                results.append({
                    "id": doc_id,
                    "document": doc,
                    "source": meta.get("source", "unknown"),
                    "score": score,
                    "metadata": meta,
                })

        except Exception as e:
            print(f"    ERROR: {e}")
            results = []

        # Compute metrics
        p = precision_at_k(results, q, k)
        r = recall_at_k(results, q, k)
        mrr = mean_reciprocal_rank(results, q)
        ndcg = ndcg_at_k(results, q, k)

        print(f"    Results: {len(results)} | P@{k}: {p:.3f} | R@{k}: {r:.3f} | MRR: {mrr:.3f} | nDCG@{k}: {ndcg:.3f}")

        # Show top results
        for j, r_item in enumerate(results[:3], 1):
            rel = "✓" if is_relevant(r_item, q) else "✗"
            src = r_item["source"][:50]
            print(f"      {j}. [{rel}] score={r_item['score']:.4f}  {src}")

        query_results.append({
            "query": q["query"],
            "description": q["description"],
            "num_results": len(results),
            "precision_at_k": p,
            "recall_at_k": r,
            "mrr": mrr,
            "ndcg_at_k": ndcg,
        })

    # Aggregate metrics
    num_queries = len(query_results)
    avg_precision = sum(q["precision_at_k"] for q in query_results) / num_queries if num_queries else 0
    avg_recall = sum(q["recall_at_k"] for q in query_results) / num_queries if num_queries else 0
    avg_mrr = sum(q["mrr"] for q in query_results) / num_queries if num_queries else 0
    avg_ndcg = sum(q["ndcg_at_k"] for q in query_results) / num_queries if num_queries else 0

    summary = {
        "mode": mode,
        "k": k,
        "collection": collection_name,
        "num_queries": num_queries,
        "avg_precision_at_k": round(avg_precision, 4),
        "avg_recall_at_k": round(avg_recall, 4),
        "avg_mrr": round(avg_mrr, 4),
        "avg_ndcg_at_k": round(avg_ndcg, 4),
        "per_query": query_results,
    }

    return summary


def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval accuracy")
    parser.add_argument("--mode", choices=["dense", "sparse", "hybrid"], default="hybrid",
                        help="Retrieval mode (default: hybrid)")
    parser.add_argument("--k", type=int, default=6, help="Top-K for metrics (default: 6)")
    parser.add_argument("--collection", default="grant_library", help="Collection name")
    parser.add_argument("--mock", action="store_true", help="Use mocked embeddings (no API key)")
    parser.add_argument("--output", help="Save results JSON to this file")
    args = parser.parse_args()

    print("=" * 60)
    print(f"RAG Retrieval Accuracy Evaluation")
    print(f"Mode: {args.mode} | K: {args.k} | Collection: {args.collection}")
    print(f"Mock: {args.mock}")
    print("=" * 60)

    if args.mock:
        # Fake embedding for testing without API key
        def _fake_embed(query: str):
            h = hash(query) & 0xFFFFFFFF
            return [((h * (i + 1)) % 1000) / 1000.0 for i in range(32)]

        with patch("backend.app.rag.retrieve.embed_query", side_effect=_fake_embed):
            summary = run_evaluation(
                mode=args.mode, k=args.k, collection_name=args.collection, use_mock=True,
            )
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("\nERROR: OPENAI_API_KEY not set. Use --mock for testing without API key.")
            sys.exit(1)
        summary = run_evaluation(
            mode=args.mode, k=args.k, collection_name=args.collection,
        )

    # Print summary
    print("\n" + "=" * 60)
    print("AGGREGATE RESULTS")
    print("=" * 60)
    print(f"  Queries evaluated:   {summary['num_queries']}")
    print(f"  Avg Precision@{args.k}:    {summary['avg_precision_at_k']:.4f}")
    print(f"  Avg Recall@{args.k}:       {summary['avg_recall_at_k']:.4f}")
    print(f"  Avg MRR:             {summary['avg_mrr']:.4f}")
    print(f"  Avg nDCG@{args.k}:         {summary['avg_ndcg_at_k']:.4f}")
    print("=" * 60)

    # Interpretation
    p = summary['avg_precision_at_k']
    if p >= 0.7:
        print("\n  Rating: EXCELLENT - Most retrieved documents are relevant")
    elif p >= 0.5:
        print("\n  Rating: GOOD - Majority of retrieved documents are relevant")
    elif p >= 0.3:
        print("\n  Rating: FAIR - Some relevant documents found, room for improvement")
    else:
        print("\n  Rating: NEEDS IMPROVEMENT - Few relevant documents being retrieved")

    # Save results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"\n  Results saved to {output_path}")


if __name__ == "__main__":
    main()
