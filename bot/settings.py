from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Читает переменные из .env (и окружения процесса).

    Это не второй конфиг: поля здесь — схема того же .env.
    Имена совпадают специально: TRACKER_ORG_ID → tracker_org_id.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MAX
    max_bot_token: str = ""
    max_webhook_secret: str = ""
    webhook_url: str = ""
    max_api_base_url: str = "https://platform-api.max.ru"

    # Яндекс Трекер
    tracker_org_id: str = ""
    tracker_queue_id: str = ""
    tracker_api_base_url: str = "https://api.tracker.yandex.net"
    tracker_auth_mode: str = "oauth"
    tracker_oauth_token: str = ""

    # LLM
    llm_provider: str = "openai"
    llm_api_base_url: str = "http://127.0.0.1:10000"
    llm_chat_url: str = "http://127.0.0.1:10000/v1/chat/completions"
    llm_api_key: str = ""
    llm_model: str = "gemma-local"
    llm_connect_timeout: float = 5.0
    llm_request_timeout: float = 90.0
    llm_max_tool_rounds: int = 6

    # STT
    stt_backend: Literal["gigaam", "stub"] = "gigaam"
    gigaam_model: str = "v3_e2e_rnnt"
    gigaam_device: str = "cuda"
    gigaam_model_dir: str = "./models/gigaam"
    stt_allow_stub: bool = True

    # Агент
    agent_require_confirm: bool = True
    agent_ask_clarify: bool = True
    agent_language: str = "ru"

    # Рантайм
    app_host: str = "0.0.0.0"
    app_port: int = 8013
    log_level: str = "INFO"

    dry_run: bool = Field(default=True, description="Без реальных вызовов Трекера/MAX")


@lru_cache
def get_settings() -> Settings:
    return Settings()
