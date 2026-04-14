import logging

from langchain_core.documents import Document

from app.services.vector_store import _encode_texts, get_collection


logger = logging.getLogger(__name__)


async def retrieve(query: str, n_results: int = 5, where: dict | None = None) -> list[Document]:
    try:
        if not query.strip():
            return []

        collection = get_collection()
        embeddings = _encode_texts([query])
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
