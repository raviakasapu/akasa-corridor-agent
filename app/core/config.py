"""Application configuration for Akasa Corridor Agent."""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App settings
    debug: bool = True
    environment: str = "development"
    app_host: str = "localhost"
    app_port: int = 8052

    # CORS
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # LLM Gateway
    llm_gateway: str = "BedrockGateway"
    llm_model: str = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

    # Multi-LLM strategy
    coordinator_model: str = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    guardian_model: str = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    manager_model: str = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    worker_model: str = "qwen.qwen3-vl-235b-a22b"

    # AWS
    aws_region: str = "us-east-1"

    # WebSocket
    ws_enabled: bool = True
    ws_token: str = ""

    # Features
    enable_prompt_caching: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
