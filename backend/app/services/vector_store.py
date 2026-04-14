from __future__ import annotations

import logging
from typing import Any

import chromadb
from FlagEmbedding import FlagModel
from langchain_core.documents import Document

from app.core.config import settings


logger = logging.getLogger(__name__)

_CLIENT: chromadb.HttpClient | None = None
_COLLECTION: Any = None
_EMBEDDING_MODEL: FlagModel | None = None

BATCH_SIZE = 100
EMBED_BATCH_SIZE = 12
EMBED_MAX_LENGTH = 8192


def _get_client() -> chromadb.HttpClient:
    global _CLIENT

    if _CLIENT is None:
        _CLIENT = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
    return _CLIENT


def _get_embedding_model() -> FlagModel:
    global _EMBEDDING_MODEL

    if _EMBEDDING_MODEL is None:
        _EMBEDDING_MODEL = FlagModel(settings.EMBEDDING_MODEL, use_fp16=True)
    return _EMBEDDING_MODEL


def _encode_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    model = _get_embedding_model()
    vectors = model.encode(
        texts,
        batch_size=EMBED_BATCH_SIZE,
        max_length=EMBED_MAX_LENGTH,
    )
    if hasattr(vectors, 'tolist'):
        return vectors.tolist()
    return list(vectors)


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

    inserted = 0
    for batch in _batched(new_docs, BATCH_SIZE):
        ids = [_chunk_id(doc) for doc in batch]
        documents = [doc.page_content for doc in batch]
        metadatas = [doc.metadata for doc in batch]
        embeddings = _encode_texts(documents)
        collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
        inserted += len(batch)

    logger.info('Ingested %s new document chunks into Chroma.', inserted)
    return inserted
