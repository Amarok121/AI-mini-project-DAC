from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / 'backend'

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.dart import load_all_documents
from app.services.vector_store import ingest_documents


def main() -> None:
    docs = load_all_documents()
    inserted = ingest_documents(docs)
    print(f'총 {len(docs)}개 청크 중 {inserted}개 신규 적재 완료')


if __name__ == '__main__':
    main()
