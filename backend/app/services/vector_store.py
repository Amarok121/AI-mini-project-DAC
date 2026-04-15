from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from app.core.config import settings


logger = logging.getLogger(__name__)

_CLIENT: Any = None
_COLLECTION: Any = None
_EMBEDDING_MODEL: Any = None

BATCH_SIZE = 100
EMBED_BATCH_SIZE = 12


def _get_client() -> Any:
    global _CLIENT

    if _CLIENT is None:
        try:
            import chromadb  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                'chromadb is not installed in this runtime. '
                'Install backend dependencies with chroma extras, or disable RAG features.'
            ) from exc
        persist_dir = Path(settings.CHROMA_PERSIST_DIR)
        persist_dir.mkdir(parents=True, exist_ok=True)
        _CLIENT = chromadb.PersistentClient(path=str(persist_dir))
    return _CLIENT


def _get_embedding_model() -> Any:
    global _EMBEDDING_MODEL

    if _EMBEDDING_MODEL is None:
        logger.info('[vector_store] 임베딩 모델 로드 중: %s', settings.EMBEDDING_MODEL)
        try:
            from FlagEmbedding import FlagModel
        except ImportError as exc:
            raise RuntimeError(
                'FlagEmbedding is not installed in this runtime. '
                'Use the ingest image or install ingest dependencies to enable local embeddings.'
            ) from exc
        _EMBEDDING_MODEL = FlagModel(settings.EMBEDDING_MODEL, use_fp16=True)
        logger.info('[vector_store] 임베딩 모델 로드 완료')
    return _EMBEDDING_MODEL


def _encode_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    model = _get_embedding_model()
    total_batches = max(1, (len(texts) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE)
    logger.info('[vector_store] %s개 청크 임베딩 시작', len(texts))
    encoded_batches: list[list[list[float]]] = []
    for index in range(0, len(texts), EMBED_BATCH_SIZE):
        batch_number = (index // EMBED_BATCH_SIZE) + 1
        logger.info('[vector_store] 임베딩 배치 %s/%s 처리 중', batch_number, total_batches)
        batch_vectors = model.encode(
            texts[index : index + EMBED_BATCH_SIZE],
            batch_size=EMBED_BATCH_SIZE,
            max_length=settings.EMBED_MAX_LENGTH,
        )
        if hasattr(batch_vectors, 'tolist'):
            encoded_batches.extend(batch_vectors.tolist())
        else:
            encoded_batches.extend(list(batch_vectors))
    logger.info('[vector_store] 임베딩 완료')
    return encoded_batches


def _chunk_id(doc: Document) -> str:
    source_file = doc.metadata.get('source_file', 'unknown')
    chunk_index = doc.metadata.get('chunk_index', 0)
    return f'{source_file}__{chunk_index}'


def get_collection():
    global _COLLECTION

    if _COLLECTION is None:
        _COLLECTION = _get_client().get_or_create_collection(
            name=settings.CHROMA_COLLECTION,
            metadata={'hnsw:space': 'cosine'},
        )
    return _COLLECTION


def _batched(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def ingest_documents(docs: list[Document]) -> int:
    if not docs:
        return 0

    collection = get_collection()
    doc_ids = [_chunk_id(doc) for doc in docs]
    existing_response = collection.get(ids=doc_ids)
    existing_ids = set(existing_response.get('ids', []))

    new_docs = [doc for doc in docs if _chunk_id(doc) not in existing_ids]
    if not new_docs:
        logger.info('No new documents to ingest.')
        return 0

    logger.info('[vector_store] Chroma 업로드 시작 (%s개 청크)', len(new_docs))
    inserted = 0
    batches = _batched(new_docs, BATCH_SIZE)
    for batch_index, batch in enumerate(batches, start=1):
        logger.info('[vector_store] 업로드 배치 %s/%s', batch_index, len(batches))
        ids = [_chunk_id(doc) for doc in batch]
        documents = [doc.page_content for doc in batch]
        metadatas = [doc.metadata for doc in batch]
        embeddings = _encode_texts(documents)
        collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
        inserted += len(batch)

    logger.info('[vector_store] 업로드 완료 — %s개 신규 적재', inserted)
    return inserted
