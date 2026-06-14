from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    OPENAI_API_KEY: str = ""
    GITHUB_WEBHOOK_SECRET: str = "supersecret"
    GITHUB_TOKEN: str = ""
    GITHUB_API_URL: str = "https://api.github.com"
    GITHUB_DEFAULT_BRANCH: str = "main"
    MODEL_NAME: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.0
    REPOSITORY_NAME: str = "owner/repo"
    TARGET_FILE_PATH: str = "tests/test_target.py"
    SANDBOX_DIR: str = "sandbox_temp"
    SANDBOX_IMAGE: str = "sandbox-tester:latest"
    SANDBOX_MEMORY_LIMIT: str = "256m"
    SANDBOX_NANO_CPUS: int = 500_000_000
    SANDBOX_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=300)
    KEYCLOAK_ENABLED: bool = False
    KEYCLOAK_ISSUER_URL: str = ""
    KEYCLOAK_AUDIENCE: str = "patchforge-api"
    KEYCLOAK_REQUIRED_ROLE: str = "patchforge-ci"
    KEYCLOAK_JWKS_URL: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
