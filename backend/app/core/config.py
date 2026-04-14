from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / '.env',
        env_file_encoding='utf-8',
        extra='ignore',
    )

    OPENAI_API_KEY: str = ''
    OPENAI_MODEL: str = 'gpt-4o-mini'
    SEMANTIC_SCHOLAR_API_KEY: str = ''
    NAVER_CLIENT_ID: str = ''
    NAVER_CLIENT_SECRET: str = ''
    NAVER_NEWS_API_URL: str = 'https://openapi.naver.com/v1/search/news.json'
    KIPRIS_API_URL: str = 'http://plus.kipris.or.kr/kipo-api/kipi'
    API_TIMEOUT_SEC: float = 20.0
    BIGKINDS_API_KEY: str = ''
    KIPRIS_API_KEY: str = ''
    TAVILY_API_KEY: str = ''
    LAW_GO_KR_API_KEY: str = ''
    # OpenAlex 권장: User-Agent에 연락용 이메일 (https://docs.openalex.org)
    OPENALEX_CONTACT_EMAIL: str = 'dev@localhost'
    DART_API_KEY: str = ''
    DART_DOCS_DIR: str = './data/dart'

    CHROMA_PERSIST_DIR: str = './data/chroma'
    CHROMA_COLLECTION: str = 'dac_docs'
    EMBEDDING_MODEL: str = 'BAAI/bge-m3'
    EMBED_MAX_LENGTH: int = 512
    TABLE_SUMMARY_ENABLED: bool = False
    REPORT_OUTPUT_DIR: str = './reports'

    CORS_ORIGINS: str = 'http://localhost:5173'


settings = Settings()
