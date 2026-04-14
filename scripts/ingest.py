from pathlib import Path
import sys
import logging


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / 'backend'
APP_DIR = ROOT_DIR

if BACKEND_DIR.exists() and str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
elif (APP_DIR / 'app').exists() and str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app.services.dart import load_all_documents
from app.services.dart import load_and_chunk
from app.services.vector_store import get_collection, ingest_documents


logger = logging.getLogger(__name__)


def _configured_docs_root() -> Path:
    from app.core.config import settings

    root = Path(settings.DART_DOCS_DIR)
    if root.exists():
        return root
    return ROOT_DIR / settings.DART_DOCS_DIR


def _existing_source_files() -> set[str]:
    try:
        collection = get_collection()
        response = collection.get(include=['metadatas'])
        metadatas = response.get('metadatas') or []
        return {
            metadata.get('source_file')
            for metadata in metadatas
            if isinstance(metadata, dict) and metadata.get('source_file')
        }
    except Exception as exc:
        logger.warning('기존 적재 파일 목록 조회 실패. 전체 스캔으로 진행합니다: %s', exc)
        return set()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format='%(message)s')

    docs_root = _configured_docs_root()
    pdf_paths = sorted(docs_root.rglob('*.pdf')) if docs_root.exists() else []
    logger.info('전체 PDF %s개 발견', len(pdf_paths))

    existing_source_files = _existing_source_files()
    skipped_paths = [path for path in pdf_paths if path.name in existing_source_files]
    target_paths = [path for path in pdf_paths if path.name not in existing_source_files]

    logger.info('이미 적재된 PDF %s개 skip', len(skipped_paths))
    logger.info('신규 파싱 대상 %s개', len(target_paths))

    if not target_paths:
        logger.info('신규 파일 없음. 종료합니다.')
        print('총 0개 청크 중 0개 신규 적재 완료')
        return

    docs = []
    for pdf_path in target_paths:
        docs.extend(load_and_chunk(str(pdf_path)))

    inserted = ingest_documents(docs)
    print(f'총 {len(docs)}개 청크 중 {inserted}개 신규 적재 완료')


if __name__ == '__main__':
    main()
