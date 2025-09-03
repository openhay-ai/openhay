from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.models.openai import OpenAIModel
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    database_url: str

    # LLM Providers
    llm_provider: Literal["openai", "anthropic", "google", "ollama"] = "google"
    llm_model: str = "gemini-2.5-flash"

    # For deep research
    lead_research_llm_model: str = "gemini-2.5-flash"
    subagent_research_llm_model: str = "gemini-2.5-flash"

    google_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Local LLM
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen3:8b"

    # Web Search
    brave_api_key: Optional[str] = None
    brave_search_url: str = "https://api.search.brave.com/res/v1/web/search"

    # Telemetry
    logfire_token: Optional[str] = None

    # SMTP / Support
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    support_owner_email: Optional[str] = None
    support_from_email: Optional[str] = None

    # Analytics / Privacy
    collect_client_ip: bool = True
    analytics_ip_salt: Optional[str] = None

    # Deployment / CORS
    host_url: Optional[str] = None
    railway_public_domain: Optional[str] = None
    # Comma-separated list of extra origins
    allowed_origins: Optional[str] = None

    # JWT Authentication
    jwt_secret_key: Optional[str] = None

    # Environment
    env: Literal["prod", "dev"] = "prod"

    # RPM
    gemini_flash_rpm: int = 5
    gemini_pro_rpm: int = 3

    @property
    def model(self) -> Model:
        if self.llm_provider == "openai":
            return OpenAIModel(model_name=self.llm_model, provider="openai")
        elif self.llm_provider == "anthropic":
            return AnthropicModel(model_name=self.llm_model)
        elif self.llm_provider == "google":
            return GoogleModel(model_name=self.llm_model)
        elif self.llm_provider == "ollama":
            from pydantic_ai.providers.ollama import OllamaProvider

            assert self.ollama_base_url is not None, "OLLAMA_BASE_URL must be set to use Ollama"
            return OpenAIModel(
                model_name=self.llm_model,
                provider=OllamaProvider(base_url=self.ollama_base_url),
            )
        else:
            raise ValueError(f"Invalid LLM: {self.llm_provider}")

    @property
    def lead_research_model(self) -> Model:
        google_settings = GoogleModelSettings(
            google_thinking_config={
                "thinking_budget": 8096,
                "include_thoughts": True,
            }
        )
        return GoogleModel(
            model_name=self.subagent_research_llm_model,
            settings=google_settings,
        )

    @property
    def subagent_research_model(self) -> Model:
        google_settings = GoogleModelSettings(
            google_thinking_config={
                "thinking_budget": 2048,
                "include_thoughts": True,
            }
        )
        return GoogleModel(
            model_name=self.subagent_research_llm_model,
            settings=google_settings,
        )


settings = Settings()
