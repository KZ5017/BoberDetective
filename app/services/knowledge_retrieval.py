from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.knowledge import KnowledgeDocumentModel
from app.schemas.knowledge import KnowledgeIndexRequest
from app.services.knowledge_import import KnowledgeStoredChunk, read_knowledge_chunks
from app.services.knowledge_indexing import KnowledgeIndexError, QdrantKnowledgeIndex, get_knowledge_index_status
from app.services.llm import LLMProviderError, get_llm_provider


KNOWLEDGE_CONTEXT_NEIGHBOR_RATIO = 0.55
KNOWLEDGE_SECTION_CONTEXT_PER_SEED_LIMIT = 10
KNOWLEDGE_HIGH_EXPANSION_THRESHOLD = 0.8
KNOWLEDGE_MEDIUM_EXPANSION_THRESHOLD = 0.6
KNOWLEDGE_HIGH_EXPANSION_LIMIT = 10
KNOWLEDGE_MEDIUM_EXPANSION_LIMIT = 6
KNOWLEDGE_DOCUMENT_SCORE_TOP_HITS = 3
KNOWLEDGE_DOCUMENT_COVERAGE_BONUS_PER_CHUNK = 0.03
KNOWLEDGE_DOCUMENT_COVERAGE_BONUS_MAX = 0.18
KNOWLEDGE_TECHNICAL_QUERY_HINTS = {
    "bash",
    "bitsadmin",
    "certutil",
    "cmd",
    "copy",
    "curl",
    "dns",
    "exe",
    "ftp",
    "http",
    "https",
    "impacket",
    "linux",
    "net",
    "powershell",
    "ps",
    "python",
    "scp",
    "smb",
    "ssh",
    "use",
    "wget",
    "windows",
}
KNOWLEDGE_STOPWORDS = {
    "a",
    "az",
    "egy",
    "és",
    "es",
    "vagy",
    "hogy",
    "mit",
    "mi",
    "milyen",
    "hogyan",
    "mikor",
    "hol",
    "van",
    "vannak",
    "kell",
    "lehet",
    "tudok",
    "tudunk",
    "keress",
    "keresd",
    "adj",
    "valasz",
    "válasz",
}


class KnowledgeRetrievalError(Exception):
    pass


class KnowledgeRetrievalValidationError(KnowledgeRetrievalError):
    pass


@dataclass(frozen=True)
class KnowledgeRetrievedChunk:
    label: str
    document: KnowledgeDocumentModel
    chunk: KnowledgeStoredChunk
    retrieval_score: float
    match_type: str


@dataclass(frozen=True)
class HeadingRelevanceScore:
    exact_query_match: bool
    term_match_count: int
    level_bonus: float
    score: float

    @property
    def is_heading_seed(self) -> bool:
        return self.exact_query_match or self.term_match_count > 0


@dataclass(frozen=True)
class KnowledgeDocumentScore:
    document_id: UUID
    score: float
    top_score_sum: float
    coverage_bonus: float
    candidate_count: int


def keyword_knowledge_search(
    documents: list[KnowledgeDocumentModel],
    query: str,
    limit: int,
) -> list[KnowledgeRetrievedChunk]:
    terms = query_terms(query)
    exact = " ".join(query.casefold().split())
    candidates: list[KnowledgeRetrievedChunk] = []
    for document in documents:
        for chunk in read_knowledge_chunks(document):
            text = " ".join(chunk.text.casefold().split())
            heading_text = " ".join(chunk.heading_path.casefold().split())
            path_text = " ".join(
                part
                for part in [
                    document.relative_path or "",
                    document.original_filename or "",
                ]
                if part
            ).casefold()
            score = 0.0
            if exact and exact in text:
                score += 2.5
            if exact and exact in heading_text:
                score += 3.0
            score += sum(1.0 for term in terms if text_contains_term(text, term))
            score += sum(1.2 for term in terms if text_contains_term(heading_text, term))
            score += min(1.5, sum(0.25 for term in terms if text_contains_term(path_text, term)))
            if score <= 0:
                continue
            candidates.append(
                KnowledgeRetrievedChunk(
                    label="",
                    document=document,
                    chunk=chunk,
                    retrieval_score=round(score, 6),
                    match_type="keyword",
                )
            )
    ranked = sorted(
        candidates,
        key=lambda item: (
            -item.retrieval_score,
            item.document.relative_path or item.document.original_filename,
            item.chunk.chunk_index,
        ),
    )[:limit]
    return relabel(ranked)


def semantic_knowledge_search(
    db: Session,
    documents: list[KnowledgeDocumentModel],
    query: str,
    limit: int,
) -> list[KnowledgeRetrievedChunk]:
    status = get_knowledge_index_status(db, KnowledgeIndexRequest(document_ids=[item.id for item in documents]))
    if status.chunk_count == 0:
        return []
    if not status.is_ready:
        raise KnowledgeRetrievalValidationError(
            "A szemantikus vagy hybrid tudásbázis kereséshez előbb indexelni kell a kijelölt tudásbázis dokumentumokat "
            f"az aktuális embedding modellel ({status.embedding_model}). "
            f"Indexelve: {status.indexed_chunk_count}/{status.chunk_count}."
        )
    settings = get_settings()
    try:
        embedding_result = get_llm_provider(settings).embeddings(settings.llm_embedding_model, [query])
        semantic_hits = QdrantKnowledgeIndex(settings).search(
            query_embedding=embedding_result.embeddings[0],
            limit=limit,
            document_ids=[item.id for item in documents],
        )
    except (LLMProviderError, KnowledgeIndexError) as exc:
        raise KnowledgeRetrievalValidationError(str(exc)) from exc
    documents_by_id = {document.id: document for document in documents}
    chunks_by_document = {document.id: {chunk.chunk_id: chunk for chunk in read_knowledge_chunks(document)} for document in documents}
    retrieved: list[KnowledgeRetrievedChunk] = []
    for hit in semantic_hits:
        document = documents_by_id.get(hit.knowledge_document_id)
        chunk = chunks_by_document.get(hit.knowledge_document_id, {}).get(hit.chunk_id)
        if document is None or chunk is None:
            continue
        retrieved.append(KnowledgeRetrievedChunk("", document, chunk, hit.score, hit.match_type))
    return relabel(retrieved)


def merge_hybrid_hits(
    keyword_hits: list[KnowledgeRetrievedChunk],
    semantic_hits: list[KnowledgeRetrievedChunk],
    limit: int,
    *,
    query: str = "",
) -> list[KnowledgeRetrievedChunk]:
    candidates: dict[tuple[UUID, str], KnowledgeRetrievedChunk] = {}
    max_keyword_score = max((hit.retrieval_score for hit in keyword_hits), default=0.0)
    for hit in keyword_hits:
        score = (hit.retrieval_score / max_keyword_score) * 0.35 if max_keyword_score > 0 else 0.0
        candidates[(hit.document.id, hit.chunk.chunk_id)] = KnowledgeRetrievedChunk(
            "",
            hit.document,
            hit.chunk,
            round(score, 6),
            "keyword",
        )
    for hit in semantic_hits:
        key = (hit.document.id, hit.chunk.chunk_id)
        semantic_score = min(1.0, max(0.0, hit.retrieval_score)) * 0.55
        existing = candidates.get(key)
        if existing is None:
            candidates[key] = KnowledgeRetrievedChunk("", hit.document, hit.chunk, round(semantic_score, 6), "semantic")
        else:
            candidates[key] = KnowledgeRetrievedChunk(
                "",
                hit.document,
                hit.chunk,
                round(existing.retrieval_score + semantic_score + 0.2, 6),
                "hybrid",
            )
    scored_candidates = [
        KnowledgeRetrievedChunk(
            "",
            hit.document,
            hit.chunk,
            round(hit.retrieval_score + markdown_hybrid_bonus(hit, query), 6),
            hit.match_type,
        )
        for hit in candidates.values()
    ]
    ranked = sorted(
        scored_candidates,
        key=lambda item: (
            -item.retrieval_score,
            item.document.relative_path or item.document.original_filename,
            item.chunk.chunk_index,
        ),
    )[:limit]
    return relabel(ranked)


def markdown_hybrid_bonus(hit: KnowledgeRetrievedChunk, query: str) -> float:
    if not query.strip():
        return 0.0
    technical_terms = technical_query_terms(query)
    normalized_query = " ".join(query.casefold().split())
    normalized_text = " ".join(hit.chunk.text.casefold().split())
    normalized_heading = " ".join(hit.chunk.heading_path.casefold().split())
    heading_score = score_heading_relevance(hit.chunk, query)

    bonus = 0.0
    if len(normalized_query) >= 4:
        if normalized_query in normalized_text:
            bonus += 0.12
    bonus += heading_score.score

    if technical_terms:
        text_technical_matches = sum(1 for term in technical_terms if text_contains_term(normalized_text, term))
        heading_technical_matches = sum(1 for term in technical_terms if text_contains_term(normalized_heading, term))
        language_matches = sum(1 for language in hit.chunk.code_languages if any(terms_match(language, term) for term in technical_terms))
        bonus += min(0.12, text_technical_matches * 0.04)
        bonus += min(0.08, heading_technical_matches * 0.04)
        bonus += min(0.08, language_matches * 0.08)
        if hit.chunk.contains_code_block and (text_technical_matches or heading_technical_matches or language_matches):
            bonus += 0.08

    return round(min(0.35, bonus), 6)


def score_heading_relevance(chunk: KnowledgeStoredChunk, query: str) -> HeadingRelevanceScore:
    terms = query_terms(query)
    normalized_query = " ".join(query.casefold().split())
    normalized_heading = " ".join(chunk.heading_path.casefold().split())
    exact_query_match = len(normalized_query) >= 4 and normalized_query in normalized_heading
    term_match_count = sum(1 for term in terms if text_contains_term(normalized_heading, term))
    base_score = (0.22 if exact_query_match else 0.0) + min(0.36, term_match_count * 0.12)
    level_bonus = heading_level_bonus(chunk.heading_level) if exact_query_match or term_match_count else 0.0
    return HeadingRelevanceScore(
        exact_query_match=exact_query_match,
        term_match_count=term_match_count,
        level_bonus=level_bonus,
        score=round(base_score + level_bonus, 6),
    )


def heading_level_bonus(heading_level: int) -> float:
    if heading_level <= 0:
        return 0.0
    if heading_level == 1:
        return 0.22
    if heading_level == 2:
        return 0.14
    if heading_level == 3:
        return 0.1
    return 0.05


def expansion_priority(hit: KnowledgeRetrievedChunk, query: str) -> float:
    if not query.strip():
        return round(hit.retrieval_score, 6)
    priority = hit.retrieval_score
    priority += score_heading_relevance(hit.chunk, query).score
    priority += path_filename_topic_bonus(hit, query)
    priority += expansion_technical_bonus(hit, query)
    return round(priority, 6)


def path_filename_topic_bonus(hit: KnowledgeRetrievedChunk, query: str) -> float:
    terms = query_terms(query)
    if not terms:
        return 0.0
    path_text = " ".join(
        part
        for part in [
            hit.document.relative_path or "",
            hit.document.original_filename or "",
        ]
        if part
    ).casefold()
    match_count = sum(1 for term in terms if text_contains_term(path_text, term))
    return round(min(0.35, match_count * 0.14), 6)


def expansion_technical_bonus(hit: KnowledgeRetrievedChunk, query: str) -> float:
    technical_terms = technical_query_terms(query)
    if not technical_terms:
        return 0.0
    normalized_text = " ".join(hit.chunk.text.casefold().split())
    normalized_heading = " ".join(hit.chunk.heading_path.casefold().split())
    text_matches = sum(1 for term in technical_terms if text_contains_term(normalized_text, term))
    heading_matches = sum(1 for term in technical_terms if text_contains_term(normalized_heading, term))
    language_matches = sum(1 for language in hit.chunk.code_languages if any(terms_match(language, term) for term in technical_terms))
    bonus = min(0.12, text_matches * 0.04)
    bonus += min(0.12, heading_matches * 0.06)
    bonus += min(0.12, language_matches * 0.12)
    if hit.chunk.contains_code_block and (text_matches or heading_matches or language_matches):
        bonus += 0.08
    return round(min(0.36, bonus), 6)


def expansion_context_limit_for_seed(hit: KnowledgeRetrievedChunk, query: str) -> int:
    priority = expansion_priority(hit, query)
    if priority >= KNOWLEDGE_HIGH_EXPANSION_THRESHOLD:
        return KNOWLEDGE_HIGH_EXPANSION_LIMIT
    if priority >= KNOWLEDGE_MEDIUM_EXPANSION_THRESHOLD:
        return KNOWLEDGE_MEDIUM_EXPANSION_LIMIT
    return 0


def technical_query_terms(query: str) -> set[str]:
    terms = set(query_terms(query))
    inline_code_terms = {item.strip().casefold() for item in re.findall(r"`([^`]+)`", query) if item.strip()}
    code_like_terms = {
        item.casefold()
        for item in re.findall(r"[A-Za-z0-9_.:/\\-]+", query)
        if any(char in item for char in "./\\:-_") or any(char.isdigit() for char in item)
    }
    technical_terms = {term for term in terms if term in KNOWLEDGE_TECHNICAL_QUERY_HINTS}
    technical_terms.update(inline_code_terms)
    technical_terms.update(code_like_terms)
    return technical_terms


def context_seed_limit(limit: int) -> int:
    neighbor_budget = context_neighbor_budget(limit)
    return max(1, limit - neighbor_budget)


def context_neighbor_budget(limit: int) -> int:
    if limit < 4:
        return 0
    return min(max(1, int(limit * KNOWLEDGE_CONTEXT_NEIGHBOR_RATIO)), max(0, limit - 1))


def expand_context_neighbors(
    documents: list[KnowledgeDocumentModel],
    seed_hits: list[KnowledgeRetrievedChunk],
    limit: int,
    *,
    query: str = "",
) -> list[KnowledgeRetrievedChunk]:
    if not seed_hits:
        return []
    neighbor_budget = min(context_neighbor_budget(limit), max(0, limit - len(seed_hits)))
    if neighbor_budget <= 0:
        return pack_retrieved_chunks_by_document(seed_hits, limit)

    seed_document_ids = {hit.document.id for hit in seed_hits}
    chunks_by_document = {
        document.id: sorted(read_knowledge_chunks(document), key=lambda chunk: chunk.chunk_index)
        for document in documents
        if document.id in seed_document_ids
    }
    selected: list[KnowledgeRetrievedChunk] = list(seed_hits[:limit])
    selected_keys = {(hit.document.id, hit.chunk.chunk_id) for hit in selected}
    added = 0
    for seed in seed_hits:
        if added >= neighbor_budget:
            break
        chunks = chunks_by_document.get(seed.document.id, [])
        per_seed_limit = expansion_context_limit_for_seed(seed, query)
        if per_seed_limit <= 0:
            continue
        section_context = section_context_for_seed(chunks, seed.chunk, query, per_seed_limit=per_seed_limit)
        heading_bridge_context = [] if section_context else heading_bridge_context_for_seed(chunks, seed.chunk, query, per_seed_limit=per_seed_limit)
        expansion_chunks = (
            section_context
            or heading_bridge_context
            or context_neighbors_for_seed(chunks, seed.chunk, per_seed_limit=per_seed_limit)
        )
        if section_context:
            match_type = "section_context"
            score_factor = 0.72
        elif heading_bridge_context:
            match_type = "heading_bridge"
            score_factor = 0.7
        else:
            match_type = "context_neighbor"
            score_factor = 0.65
        for distance, neighbor in enumerate(expansion_chunks, start=1):
            if added >= neighbor_budget:
                break
            key = (seed.document.id, neighbor.chunk_id)
            if key in selected_keys:
                continue
            selected.append(
                KnowledgeRetrievedChunk(
                    "",
                    seed.document,
                    neighbor,
                    round(max(seed.retrieval_score * score_factor * (0.94 ** (distance - 1)), 0.000001), 6),
                    match_type,
                )
            )
            selected_keys.add(key)
            added += 1
    return pack_retrieved_chunks_by_document(selected, limit)


def pack_retrieved_chunks_by_document(
    candidates: list[KnowledgeRetrievedChunk],
    limit: int,
) -> list[KnowledgeRetrievedChunk]:
    if limit <= 0 or not candidates:
        return []
    grouped: dict[UUID, dict[str, KnowledgeRetrievedChunk]] = {}
    documents: dict[UUID, KnowledgeDocumentModel] = {}
    for candidate in candidates:
        documents[candidate.document.id] = candidate.document
        chunk_group = grouped.setdefault(candidate.document.id, {})
        existing = chunk_group.get(candidate.chunk.chunk_id)
        if existing is None or candidate.retrieval_score > existing.retrieval_score:
            chunk_group[candidate.chunk.chunk_id] = candidate

    document_scores = {
        document_id: score_document_candidates(list(chunk_group.values()))
        for document_id, chunk_group in grouped.items()
    }
    ordered_document_ids = sorted(
        grouped,
        key=lambda document_id: (
            -document_scores[document_id].score,
            documents[document_id].relative_path or documents[document_id].original_filename,
            documents[document_id].original_filename,
        ),
    )
    packed: list[KnowledgeRetrievedChunk] = []
    for document_id in ordered_document_ids:
        for candidate in sorted(grouped[document_id].values(), key=lambda item: item.chunk.chunk_index):
            packed.append(candidate)
            if len(packed) >= limit:
                return relabel(packed)
    return relabel(packed)


def score_document_candidates(candidates: list[KnowledgeRetrievedChunk]) -> KnowledgeDocumentScore:
    if not candidates:
        return KnowledgeDocumentScore(UUID(int=0), 0.0, 0.0, 0.0, 0)
    top_score_sum = sum(
        sorted((candidate.retrieval_score for candidate in candidates), reverse=True)[:KNOWLEDGE_DOCUMENT_SCORE_TOP_HITS]
    )
    coverage_bonus = min(
        KNOWLEDGE_DOCUMENT_COVERAGE_BONUS_MAX,
        max(0, len(candidates) - 1) * KNOWLEDGE_DOCUMENT_COVERAGE_BONUS_PER_CHUNK,
    )
    score = round(top_score_sum + coverage_bonus, 6)
    return KnowledgeDocumentScore(
        document_id=candidates[0].document.id,
        score=score,
        top_score_sum=round(top_score_sum, 6),
        coverage_bonus=round(coverage_bonus, 6),
        candidate_count=len(candidates),
    )


def section_context_for_seed(
    chunks: list[KnowledgeStoredChunk],
    seed_chunk: KnowledgeStoredChunk,
    query: str,
    *,
    per_seed_limit: int = KNOWLEDGE_SECTION_CONTEXT_PER_SEED_LIMIT,
) -> list[KnowledgeStoredChunk]:
    if per_seed_limit <= 0 or not score_heading_relevance(seed_chunk, query).is_heading_seed:
        return []
    index_by_chunk_id = {chunk.chunk_id: index for index, chunk in enumerate(chunks)}
    seed_position = index_by_chunk_id.get(seed_chunk.chunk_id)
    if seed_position is None:
        return []
    context_chunks: list[KnowledgeStoredChunk] = []
    for candidate in chunks[seed_position + 1 :]:
        if not compatible_heading_path(seed_chunk.heading_path, candidate.heading_path):
            break
        context_chunks.append(candidate)
        if len(context_chunks) >= per_seed_limit:
            break
    return context_chunks


def heading_bridge_context_for_seed(
    chunks: list[KnowledgeStoredChunk],
    seed_chunk: KnowledgeStoredChunk,
    query: str,
    *,
    per_seed_limit: int = KNOWLEDGE_MEDIUM_EXPANSION_LIMIT,
) -> list[KnowledgeStoredChunk]:
    if per_seed_limit <= 0 or not query.strip():
        return []
    if seed_chunk.heading_path.strip():
        return []
    index_by_chunk_id = {chunk.chunk_id: index for index, chunk in enumerate(chunks)}
    seed_position = index_by_chunk_id.get(seed_chunk.chunk_id)
    if seed_position is None:
        return []

    first_matching: KnowledgeStoredChunk | None = None
    for candidate in chunks[seed_position + 1 :]:
        if not candidate.heading_path.strip():
            continue
        if not score_heading_relevance(candidate, query).is_heading_seed:
            return []
        first_matching = candidate
        break
    if first_matching is None:
        return []

    context_chunks: list[KnowledgeStoredChunk] = []
    for candidate in chunks[index_by_chunk_id[first_matching.chunk_id] :]:
        if not score_heading_relevance(candidate, query).is_heading_seed:
            break
        context_chunks.append(candidate)
        if len(context_chunks) >= per_seed_limit:
            break
    return context_chunks


def context_neighbors_for_seed(
    chunks: list[KnowledgeStoredChunk],
    seed_chunk: KnowledgeStoredChunk,
    *,
    per_seed_limit: int = KNOWLEDGE_MEDIUM_EXPANSION_LIMIT,
) -> list[KnowledgeStoredChunk]:
    if per_seed_limit <= 0:
        return []
    index_by_chunk_id = {chunk.chunk_id: index for index, chunk in enumerate(chunks)}
    seed_position = index_by_chunk_id.get(seed_chunk.chunk_id)
    if seed_position is None:
        return []
    neighbors: list[KnowledgeStoredChunk] = []
    for neighbor_position in range(seed_position + 1, len(chunks)):
        if neighbor_position < 0 or neighbor_position >= len(chunks):
            continue
        neighbor = chunks[neighbor_position]
        if not compatible_heading_path(seed_chunk.heading_path, neighbor.heading_path):
            break
        neighbors.append(neighbor)
        if len(neighbors) >= per_seed_limit:
            break
    return neighbors


def compatible_heading_path(first: str, second: str) -> bool:
    first_parts = heading_parts(first)
    second_parts = heading_parts(second)
    if not first_parts or not second_parts:
        return first_parts == second_parts
    shortest = min(len(first_parts), len(second_parts))
    return first_parts[:shortest] == second_parts[:shortest]


def heading_parts(value: str) -> list[str]:
    return [part.strip().casefold() for part in value.split(">") if part.strip()]


def order_retrieved_chunks_for_llm(retrieved_chunks: list[KnowledgeRetrievedChunk]) -> list[KnowledgeRetrievedChunk]:
    return pack_retrieved_chunks_by_document(retrieved_chunks, len(retrieved_chunks))


def query_terms(query: str) -> list[str]:
    terms: list[str] = []
    for term in re.findall(r"[\wáéíóöőúüűÁÉÍÓÖŐÚÜŰ'-]+", query.casefold()):
        if len(term) < 2 or term in KNOWLEDGE_STOPWORDS:
            continue
        terms.append(term)
    return list(dict.fromkeys(terms))


def text_contains_term(text: str, term: str) -> bool:
    normalized_text = text.casefold()
    normalized_term = term.casefold()
    if normalized_term in normalized_text:
        return True
    text_terms = re.findall(r"[\wáéíóöőúüűÁÉÍÓÖŐÚÜŰ'-]+", normalized_text)
    return any(terms_match(candidate, normalized_term) for candidate in text_terms)


def terms_match(left: str, right: str) -> bool:
    first = left.casefold().strip()
    second = right.casefold().strip()
    if not first or not second:
        return False
    if first == second:
        return True
    shortest = min(len(first), len(second))
    if shortest < 5:
        return False
    return first.startswith(second[:shortest]) or second.startswith(first[:shortest])


def relabel(retrieved_chunks: list[KnowledgeRetrievedChunk]) -> list[KnowledgeRetrievedChunk]:
    return [
        KnowledgeRetrievedChunk(
            label=f"source_{index}",
            document=retrieved.document,
            chunk=retrieved.chunk,
            retrieval_score=retrieved.retrieval_score,
            match_type=retrieved.match_type,
        )
        for index, retrieved in enumerate(retrieved_chunks, start=1)
    ]
