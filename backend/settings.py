from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    database_url: str

    # LLM Providers
    llm: Literal["openai", "anthropic", "google", "ollama"] = "google"
    google_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_model: str = "qwen3:8b"

    # Web Search
    brave_api_key: Optional[str] = None
    brave_search_url: str = "https://api.search.brave.com/res/v1/web/search"

    # Telemetry
    logfire_write_token: Optional[str] = None

    @property
    def model_name(self) -> str:
        if self.llm == "openai":
            return "openai:gpt-4o"
        elif self.llm == "anthropic":
            return "anthropic:claude-4-sonnet-20250514"
        elif self.llm == "google":
            return "google-gla:gemini-2.5-flash"
        elif self.llm == "ollama":
            return self.ollama_model
        else:
            raise ValueError(f"Invalid LLM: {self.llm}")


settings = Settings()
