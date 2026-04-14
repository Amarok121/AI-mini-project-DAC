from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    OPENAI_API_KEY: str = ''
    OPENAI_MODEL: str = 'gpt-4o-mini'
    SEMANTIC_SCHOLAR_API_KEY: str = ''
    BIGKINDS_API_KEY: str = ''
    KIPRIS_API_KEY: str = ''
    TAVILY_API_KEY: str = ''
    LAW_GO_KR_API_KEY: str = ''
    # OpenAlex 권장: User-Agent에 연락용 이메일 (https://docs.openalex.org)
    OPENALEX_CONTACT_EMAIL: str = 'dev@localhost'
    DART_API_KEY: str = ''
    DART_DOCS_DIR: str = './data/dart'

    CHROMA_HOST: str = 'chroma'
    CHROMA_PORT: int = 8000

    CORS_ORIGINS: str = 'http://localhost:5173'


settings = Settings()
