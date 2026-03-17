from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, List, Sequence

from backend.app.compliance.models import ComplianceCheck, RetrievedContext, SectionContext, SourceChunk
from backend.app.compliance.storage import load_checks, load_chunks


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _cosineish_score(query_tokens: Sequence[str], doc_tokens: Sequence[str]) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0
    q_counts = Counter(query_tokens)
    d_counts = Counter(doc_tokens)
    overlap = sum(q_counts[token] * d_counts[token] for token in q_counts.keys() & d_counts.keys())
    q_norm = math.sqrt(sum(value * value for value in q_counts.values()))
    d_norm = math.sqrt(sum(value * value for value in d_counts.values()))
    if not q_norm or not d_norm:
        return 0.0
    return overlap / (q_norm * d_norm)


class LocalHybridRetriever:
    """Metadata-first lexical retriever that can be swapped for a vector backend later."""

    def __init__(self, checks: Iterable[ComplianceCheck] | None = None, chunks: Iterable[SourceChunk] | None = None) -> None:
        self.checks = list(checks) if checks is not None else load_checks()
        self.chunks = list(chunks) if chunks is not None else load_chunks()

    def retrieve(self, context: SectionContext, checks_top_k: int = 4, excerpts_top_k: int = 2) -> RetrievedContext:
        return RetrievedContext(
            checks=self._retrieve_checks(context, top_k=checks_top_k),
            excerpts=self._retrieve_excerpts(context, top_k=excerpts_top_k),
        )

    def _retrieve_checks(self, context: SectionContext, top_k: int) -> List[ComplianceCheck]:
        filtered = [check for check in self.checks if self._check_matches_context(check, context)]
        query_tokens = _tokenize(" ".join([context.section_name, context.section_text, *context.section_tags, *context.framework_tags]))
        ranked = sorted(
            filtered,
            key=lambda item: self._score_check(item, context, query_tokens),
            reverse=True,
        )
        return ranked[:top_k]

    def _retrieve_excerpts(self, context: SectionContext, top_k: int) -> List[SourceChunk]:
        filtered = [chunk for chunk in self.chunks if self._chunk_matches_context(chunk, context)]
        query_tokens = _tokenize(" ".join([context.section_name, context.section_text, *context.section_tags, *context.framework_tags]))
        ranked = sorted(
            filtered,
            key=lambda item: self._score_chunk(item, context, query_tokens),
            reverse=True,
        )
        return ranked[:top_k]

    def _check_matches_context(self, check: ComplianceCheck, context: SectionContext) -> bool:
        section_match = check.section == context.normalized_section or check.category in context.section_tags
        if not section_match:
            return False
        if context.is_inuit_specific:
            return True
        return "Inuit" not in check.community_scope or any(scope != "Inuit" for scope in check.community_scope)

    def _chunk_matches_context(self, chunk: SourceChunk, context: SectionContext) -> bool:
        section_match = bool(set(chunk.section_tags) & set(context.section_tags)) or context.normalized_section in chunk.section_tags
        if not section_match:
            return False
        if context.is_inuit_specific:
            return True
        return "Inuit" not in chunk.community_scope or any(scope != "Inuit" for scope in chunk.community_scope)

    def _score_check(self, check: ComplianceCheck, context: SectionContext, query_tokens: Sequence[str]) -> float:
        text = " ".join(
            [
                check.title,
                check.check_text,
                check.explanation,
                " ".join(check.failure_signals),
                " ".join(check.framework_tags),
                " ".join(check.community_scope),
            ]
        )
        lexical = _cosineish_score(query_tokens, _tokenize(text))
        priority_bonus = {"core": 0.35, "secondary": 0.15, "low_priority": 0.05}.get(self._priority_from_weight(check.priority_weight), 0.0)
        section_bonus = 0.25 if check.section == context.normalized_section else 0.0
        inuit_bonus = 0.2 if context.is_inuit_specific and "Inuit" in check.community_scope else 0.0
        return lexical + priority_bonus + section_bonus + inuit_bonus + check.priority_weight * 0.1

    def _score_chunk(self, chunk: SourceChunk, context: SectionContext, query_tokens: Sequence[str]) -> float:
        text = " ".join([chunk.title, chunk.brief_description, chunk.chunk_text, " ".join(chunk.framework_tags)])
        lexical = _cosineish_score(query_tokens, _tokenize(text))
        priority_bonus = {"core": 0.3, "secondary": 0.12, "low_priority": 0.04}.get(chunk.priority_level, 0.0)
        section_bonus = 0.2 if bool(set(chunk.section_tags) & set(context.section_tags)) else 0.0
        inuit_bonus = 0.2 if context.is_inuit_specific and "Inuit" in chunk.community_scope else 0.0
        return lexical + priority_bonus + section_bonus + inuit_bonus

    @staticmethod
    def _priority_from_weight(weight: float) -> str:
        if weight >= 0.9:
            return "core"
        if weight >= 0.6:
            return "secondary"
        return "low_priority"
