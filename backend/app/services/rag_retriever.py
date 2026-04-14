import logging
from typing import Any

from langchain_core.documents import Document

from app.core.config import settings
from app.services.vector_store import get_collection


logger = logging.getLogger(__name__)
_RETRIEVER_MODEL: Any = None


def _get_retriever_model() -> Any:
    global _RETRIEVER_MODEL

    if _RETRIEVER_MODEL is None:
        try:
            from FlagEmbedding import FlagModel
        except ImportError as exc:
            logger.exception('FlagEmbedding is not installed; retrieval will return empty results.')
            raise RuntimeError('FlagEmbedding is not installed in this runtime.') from exc
        logger.info('[rag_retriever] 쿼리 임베딩 모델 로드 중: %s', settings.EMBEDDING_MODEL)
        _RETRIEVER_MODEL = FlagModel(settings.EMBEDDING_MODEL, use_fp16=True)
        logger.info('[rag_retriever] 쿼리 임베딩 모델 로드 완료')

    return _RETRIEVER_MODEL


def _encode_query(query: str) -> list[list[float]]:
    if not query.strip():
        return []

    model = _get_retriever_model()
    embeddings = model.encode(
        [query],
        batch_size=1,
        max_length=settings.EMBED_MAX_LENGTH,
    )
    if hasattr(embeddings, 'tolist'):
        return embeddings.tolist()
    return list(embeddings)


async def retrieve(query: str, n_results: int = 5, where: dict | None = None) -> list[Document]:
    try:
        if not query.strip():
            return []

        collection = get_collection()
        embeddings = _encode_query(query)
        response = collection.query(
            query_embeddings=embeddings,
            n_results=n_results,
            where=where,
        )

        documents = response.get('documents', [[]])
        metadatas = response.get('metadatas', [[]])
        paired_docs = zip(documents[0] if documents else [], metadatas[0] if metadatas else [])

        return [
            Document(page_content=page_content, metadata=metadata or {})
            for page_content, metadata in paired_docs
        ]
    except Exception:
        logger.exception('Failed to retrieve RAG context for query: %s', query)
        return []


async def get_context_string(query: str, n_results: int = 5) -> str:
    try:
        docs = await retrieve(query=query, n_results=n_results, where=None)
        if not docs:
            return ''

        return '\n\n'.join(
            [
                f"[Source: {doc.metadata.get('source_file', 'unknown')}, Chunk: {doc.metadata.get('chunk_index', 'unknown')}]\n{doc.page_content}"
                for doc in docs
            ]
        )
    except Exception:
        logger.exception('Failed to build context string for query: %s', query)
        return ''


async def retrieve_context(company_name: str, query: str) -> list[str]:
    docs = await retrieve(query=query, where={'company': company_name})
    return [doc.page_content for doc in docs]
