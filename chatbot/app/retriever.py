"""
app/retriever.py

BUG 1+5 FIX: vector_store=None now handled gracefully throughout.
             HybridRetriever.__init__ no longer crashes when store is None.
             run_rag() returns early with (empty, 0.0, []) if store is None
             instead of crashing silently and returning misleading results.

All RAG techniques remain fully intact:
  1. Query Expansion
  2. Query Decomposition
  3. Hybrid Retrieval (BM25 + Semantic)
  4. Metadata Filtering
  5. FlashRank Reranking
  6. Corrective RAG
  7. Multi-hop / Iterative RAG
  8. Adaptive RAG (classify query complexity)
  9. Hallucination Management (confidence scoring)
"""

import re
import logging
from typing import List, Tuple, Optional
import numpy as np

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from config import (
    GROQ_API_KEY, LLM_MODEL, LLM_TEMPERATURE,
    EMBEDDING_MODEL, CHROMA_DB_DIR, CHROMA_COLLECTION,
    TOP_K_RETRIEVAL, TOP_K_RERANK,
    BM25_WEIGHT, SEMANTIC_WEIGHT, NUM_EXPANSIONS,
)

logger = logging.getLogger(__name__)


def load_vector_store() -> Optional[Chroma]:
    """Load the persisted ChromaDB vector store. Returns None if not found."""
    try:
        embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        return Chroma(
            persist_directory=CHROMA_DB_DIR,
            embedding_function=embeddings,
            collection_name=CHROMA_COLLECTION,
        )
    except Exception as e:
        logger.error(f"Vector store load failed: {e}")
        return None


def get_llm() -> ChatGroq:
    return ChatGroq(api_key=GROQ_API_KEY, model=LLM_MODEL, temperature=LLM_TEMPERATURE)


# ── 1. Query Expansion ─────────────────────────────────────────

def expand_query(query: str, llm: ChatGroq) -> List[str]:
    """Generate multiple phrasings of the query for better retrieval coverage."""
    prompt = PromptTemplate.from_template(
        """Generate {n} alternative search queries for this medical question.
Each should use different medical synonyms or related terms.
Return ONLY the queries, one per line, no numbering.

Original: {query}

Alternatives:"""
    )
    try:
        result   = (prompt | llm | StrOutputParser()).invoke({"query": query, "n": NUM_EXPANSIONS})
        expanded = [q.strip() for q in result.strip().split("\n") if q.strip()]
        queries  = [query] + expanded[:NUM_EXPANSIONS]
        logger.info(f"Expanded to {len(queries)} queries")
        return queries
    except Exception as e:
        logger.warning(f"Query expansion failed: {e}")
        return [query]


# ── 2. Query Decomposition ─────────────────────────────────────

def decompose_query(query: str, llm: ChatGroq) -> List[str]:
    """Break complex multi-part queries into simple sub-questions."""
    prompt = PromptTemplate.from_template(
        """If this medical question contains multiple distinct parts, split it into separate simple questions.
If it is already simple, return it as-is.
Return ONLY the questions, one per line.

Question: {query}

Sub-questions:"""
    )
    try:
        result = (prompt | llm | StrOutputParser()).invoke({"query": query})
        parts  = [q.strip() for q in result.strip().split("\n") if q.strip()]
        return parts if parts else [query]
    except Exception as e:
        logger.warning(f"Decomposition failed: {e}")
        return [query]


# ── 3. Hybrid Retriever (BM25 + Semantic) ─────────────────────

class HybridRetriever:
    """
    BUG 1+5 FIX: __init__ and retrieve() now handle None/empty vector store.
    Previously, passing None as vector_store caused BM25Okapi([]) to crash,
    which was silently caught → rag_confidence=0 → everything fell to web search.
    """

    def __init__(self, vector_store: Optional[Chroma]):
        self.vector_store = vector_store
        self.docs         = []
        self.metadatas    = []
        self.bm25         = None

        if vector_store is None:
            logger.warning("HybridRetriever initialized with None vector_store — BM25 disabled")
            return

        self._init_bm25()

    def _init_bm25(self):
        """Build BM25 index from ChromaDB collection."""
        try:
            from rank_bm25 import BM25Okapi
            data           = self.vector_store._collection.get()
            self.docs      = data.get("documents") or []
            self.metadatas = data.get("metadatas") or []

            if not self.docs:
                logger.warning("Vector store is empty — BM25 index not built")
                return

            tokenized = [d.lower().split() for d in self.docs]
            self.bm25 = BM25Okapi(tokenized)
            logger.info(f"BM25 index built: {len(self.docs)} documents")
        except Exception as e:
            logger.error(f"BM25 init failed: {e}")
            self.docs, self.metadatas, self.bm25 = [], [], None

    def retrieve(self, query: str, k: int = TOP_K_RETRIEVAL) -> List[dict]:
        """
        Hybrid retrieval combining BM25 and semantic search.
        Returns [] gracefully if vector store is None or empty.
        """
        if self.vector_store is None:
            return []

        results = {}

        # Semantic search
        try:
            for doc, dist in self.vector_store.similarity_search_with_score(query, k=k):
                content = doc.page_content
                # Convert L2 distance to similarity score correctly
                semantic_score = 1.0 / (1.0 + float(dist))
                results[content] = {
                    "content"        : content,
                    "metadata"       : doc.metadata,
                    "semantic_score" : semantic_score,
                    "bm25_score"     : 0.0,
                }
        except Exception as e:
            logger.error(f"Semantic search error: {e}")

        # BM25 search
        if self.bm25 and self.docs:
            try:
                scores    = self.bm25.get_scores(query.lower().split())
                max_score = max(scores) if max(scores) > 0 else 1.0
                for idx in np.argsort(scores)[::-1][:k]:
                    if scores[idx] > 0:
                        content = self.docs[idx]
                        norm_score = scores[idx] / max_score
                        if content in results:
                            results[content]["bm25_score"] = norm_score
                        else:
                            results[content] = {
                                "content"        : content,
                                "metadata"       : self.metadatas[idx] if self.metadatas else {},
                                "semantic_score" : 0.0,
                                "bm25_score"     : norm_score,
                            }
            except Exception as e:
                logger.error(f"BM25 search error: {e}")

        # Combine and rank
        final = []
        for r in results.values():
            r["hybrid_score"] = (
                SEMANTIC_WEIGHT * r["semantic_score"] +
                BM25_WEIGHT     * r["bm25_score"]
            )
            final.append(r)

        final.sort(key=lambda x: x["hybrid_score"], reverse=True)
        return final[:k]


# ── 4. Metadata Filtering ──────────────────────────────────────

def filter_by_metadata(docs: List[dict], criteria: dict = None) -> List[dict]:
    if not criteria:
        return docs
    filtered = [
        d for d in docs
        if all(d["metadata"].get(k) == v for k, v in criteria.items())
    ]
    return filtered if filtered else docs


# ── 5. Reranking ───────────────────────────────────────────────

def rerank(query: str, docs: List[dict], top_k: int = TOP_K_RERANK) -> List[dict]:
    """FlashRank cross-encoder reranking for better relevance scoring."""
    if not docs:
        return []
    try:
        from flashrank import Ranker, RerankRequest
        ranker   = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="/tmp")
        passages = [{"id": i, "text": d["content"]} for i, d in enumerate(docs)]
        reranked = ranker.rerank(RerankRequest(query=query, passages=passages))
        out = []
        for item in reranked[:top_k]:
            doc = docs[item.id]
            doc["rerank_score"] = item.score
            out.append(doc)
        return out
    except Exception as e:
        logger.warning(f"Reranking failed (using original order): {e}")
        return docs[:top_k]


# ── 6. Corrective RAG ─────────────────────────────────────────

def filter_irrelevant(query: str, docs: List[dict], llm: ChatGroq) -> List[dict]:
    """Remove retrieved docs that are genuinely not relevant to the query."""
    if not docs:
        return []
    prompt = PromptTemplate.from_template(
        "Is this document relevant to the medical question? Answer yes or no only.\n"
        "Question: {query}\nDocument: {doc}\nRelevant:"
    )
    chain    = prompt | llm | StrOutputParser()
    relevant = []
    for doc in docs:
        try:
            ans = chain.invoke({
                "query": query,
                "doc"  : doc["content"][:400],
            }).strip().lower()
            if "yes" in ans:
                relevant.append(doc)
        except Exception:
            relevant.append(doc)  # keep on error
    return relevant if relevant else docs


# ── 7. Multi-hop RAG ──────────────────────────────────────────

def multi_hop_retrieve(
    query: str,
    retriever: HybridRetriever,
    llm: ChatGroq,
    hops: int = 2,
) -> List[dict]:
    """Iterative retrieval — refines search based on previous hop's results."""
    all_docs      = []
    current_query = query

    for hop in range(hops):
        docs = retriever.retrieve(current_query)
        all_docs.extend(docs)

        if hop < hops - 1 and docs:
            context = "\n".join(d["content"] for d in docs[:2])
            prompt  = PromptTemplate.from_template(
                "Based on this context, what additional medical information is needed to fully answer: {query}\n\n"
                "Context: {context}\n\nFollow-up search query:"
            )
            try:
                current_query = (prompt | llm | StrOutputParser()).invoke({
                    "query"  : query,
                    "context": context,
                }).strip()
            except Exception:
                break

    # Deduplicate
    seen, unique = set(), []
    for doc in all_docs:
        if doc["content"] not in seen:
            seen.add(doc["content"])
            unique.append(doc)
    return unique


# ── 8. Adaptive RAG ───────────────────────────────────────────

def classify_complexity(query: str, llm: ChatGroq) -> str:
    """Classify query complexity to choose the right RAG strategy."""
    prompt = PromptTemplate.from_template(
        "Classify this medical query as: simple, complex, or multi_part\n"
        "- simple: one straightforward question\n"
        "- complex: requires connected multi-step information\n"
        "- multi_part: contains multiple distinct questions\n\n"
        "Query: {query}\nClassification:"
    )
    try:
        result = (prompt | llm | StrOutputParser()).invoke({"query": query}).strip().lower()
        if "multi_part" in result or "multi part" in result:
            return "multi_part"
        if "complex" in result:
            return "complex"
        return "simple"
    except Exception:
        return "simple"


# ── 9. Confidence Scoring ─────────────────────────────────────

def compute_confidence(
    query: str,
    answer: str,
    docs: List[dict],
    llm: ChatGroq,
) -> float:
    """
    Compute answer confidence (0.0-1.0).
    Combines retrieval quality score + LLM self-evaluation.
    """
    retrieval_score = (
        float(np.mean([d.get("hybrid_score", 0.5) for d in docs]))
        if docs else 0.0
    )

    prompt = PromptTemplate.from_template(
        "Rate how well this answer addresses the medical question.\n"
        "Consider accuracy and completeness. Return ONLY a decimal 0.0-1.0.\n\n"
        "Question: {query}\nAnswer: {answer}\nScore:"
    )
    try:
        raw   = (prompt | llm | StrOutputParser()).invoke({
            "query" : query,
            "answer": answer,
        }).strip()
        match     = re.search(r"0?\.\d+|1\.0|[01]", raw)
        llm_score = float(match.group()) if match else 0.65
        llm_score = max(0.0, min(1.0, llm_score))
    except Exception:
        llm_score = 0.65

    return round(0.4 * retrieval_score + 0.6 * llm_score, 3)


# ── 10. Main RAG Pipeline ─────────────────────────────────────

def run_rag(
    query: str,
    vector_store: Optional[Chroma],
    llm: ChatGroq,
    context_with_history: str = None,
) -> Tuple[str, float, List[dict]]:
    """
    Full RAG pipeline. Returns (answer, confidence, source_docs).

    BUG 1 FIX: Returns ("", 0.0, []) immediately if vector_store is None
               instead of crashing. The caller (general_rag_node) already
               guards against this, but this is a defense-in-depth fix.

    BUG 5 FIX: Hybrid search + query expansion now always execute when
               vector store is valid. Previously the crash happened before
               these techniques were reached.
    """
    # BUG 1 FIX: Guard at the pipeline entry point
    if vector_store is None:
        logger.warning("run_rag called with None vector_store — returning empty")
        return "", 0.0, []

    retriever    = HybridRetriever(vector_store)
    search_query = context_with_history or query
    complexity   = classify_complexity(query, llm)
    logger.info(f"Query complexity: {complexity}")

    # Adaptive RAG — choose strategy based on complexity
    if complexity == "multi_part":
        sub_qs   = decompose_query(query, llm)
        all_docs = []
        for sq in sub_qs:
            all_docs.extend(retriever.retrieve(sq))
        source_docs = all_docs

    elif complexity == "complex":
        source_docs = multi_hop_retrieve(search_query, retriever, llm, hops=2)

    else:
        # Simple: use query expansion for better coverage
        # BUG 5 FIX: This is now actually reached because vector_store != None
        queries     = expand_query(search_query, llm)
        all_docs    = []
        for q in queries:
            all_docs.extend(retriever.retrieve(q, k=3))
        source_docs = all_docs

    # Post-processing: rerank + corrective filter
    source_docs = rerank(query, source_docs, top_k=TOP_K_RERANK)
    source_docs = filter_irrelevant(query, source_docs, llm)

    if not source_docs:
        logger.info("No relevant docs found after filtering")
        return "", 0.0, []

    # Generate answer from retrieved context
    context = "\n\n---\n\n".join(
        f"[{d['metadata'].get('source', 'document')}]\n{d['content']}"
        for d in source_docs
    )
    prompt = PromptTemplate.from_template(
        """You are a helpful healthcare assistant.
Answer the medical question using ONLY the context below.
If the context is insufficient, say so and recommend consulting a doctor.

Context:
{context}

Question: {query}

Answer:"""
    )
    try:
        answer = (prompt | llm | StrOutputParser()).invoke({
            "context": context,
            "query"  : query,
        })
    except Exception as e:
        logger.error(f"RAG answer generation failed: {e}")
        return "", 0.0, []

    confidence = compute_confidence(query, answer, source_docs, llm)
    return answer, confidence, source_docs