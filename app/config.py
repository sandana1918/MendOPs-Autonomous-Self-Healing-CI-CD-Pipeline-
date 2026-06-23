from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    AI_API_KEY: str = ""
    AI_BASE_URL: str = ""
    OPENAI_API_KEY: str = ""
    GITHUB_WEBHOOK_SECRET: str = "supersecret"
    GITHUB_TOKEN: str = ""
    GITHUB_API_URL: str = "https://api.github.com"
    GITHUB_DEFAULT_BRANCH: str = "main"
    MODEL_NAME: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.0
    MAX_PATCH_ATTEMPTS: int = Field(default=3, ge=1, le=5)
    DEMO_PATCH_FALLBACK: bool = False
    REPOSITORY_NAME: str = "owner/repo"
    TARGET_FILE_PATH: str = "tests/test_target.py"
    TARGET_FILE_PATHS: str = ""
    SANDBOX_DIR: str = "sandbox_temp"
    SANDBOX_IMAGE: str = "sandbox-tester:latest"
    SANDBOX_MEMORY_LIMIT: str = "256m"
    SANDBOX_NANO_CPUS: int = 500_000_000
    SANDBOX_TIMEOUT_SECONDS: int = Field(default=30, ge=1, le=300)
    # docker = hardened container, local = restricted subprocess fallback,
    # auto = use Docker when reachable, otherwise fall back to local.
    SANDBOX_BACKEND: str = "auto"
    KEYCLOAK_ENABLED: bool = False
    KEYCLOAK_ISSUER_URL: str = ""
    KEYCLOAK_AUDIENCE: str = "patchforge-api"
    KEYCLOAK_REQUIRED_ROLE: str = "patchforge-ci"
    KEYCLOAK_JWKS_URL: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
