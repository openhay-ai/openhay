from typing import Literal, Optional
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.models.openai import OpenAIModel
from pydantic_settings import BaseSettings

# load_dotenv()
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load the .env file from the backend directory
load_dotenv(os.path.join(BASE_DIR, 'backend/.env'))


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

    # Email provider (prod: use https provider like resend)
    email_provider: Literal["smtp", "resend"] = "smtp"
    resend_api_key: Optional[str] = None

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
    access_token_expire_days: int = 7
    guest_token_expire_hours: int = 24
    refresh_token_expire_days: int = 30

    # Environment
    env: Literal["prod", "dev"] = "prod"

    # Discover sources config
    discover_sources_config: list[dict] = [
        {
            "url": "https://kenh14.vn",
            # These will be used for crawl4ai deep crawling.
            # Adding more sites if needed.
            # More info: https://docs.crawl4ai.com/core/deep-crawling/#41-basic-url-pattern-filter
            "max_depth": 1,
            "max_pages": 50,
            "patterns": [
                r"^https?://(?:www\.)?kenh14\.vn/.+?-\d{17,18}\.chn$",
            ],
            "category": "Giải trí",
            "target_prompt": "Prioritize Genz-focused, viral content from Kenh14.vn, zeroing in on celebrity-centric news (Sao Việt, K-pop, Cbiz), showbiz scandals, and 'nóng trên mạng' trends. Select posts with high engagement potential, strong visuals, and a fast-paced, youth-oriented tone. Include fashion/beauty/lifestyle stories only if they feature major influencers or are globally trending. Strictly filter out hard news, politics, and serious social commentary unless directly tied to a major celebrity controversy.",
        },
        {
            "url": "https://vnexpress.net",
            "max_depth": 1,
            "max_pages": 50,
            "patterns": [
                ".html",
            ],
            "category": "Thời sự",
            "target_prompt": "Curate top-impact, breaking news from VnExpress focusing on Current Affairs (Thời sự), World (Thế giới), Business (Kinh doanh), and Law (Pháp luật). Prioritize articles with significant national or international implications, major policy changes, or market-moving business developments. Exclude soft news, local-only stories, sports, and entertainment unless of major national importance.",
        },
        {
            "url": "https://cafef.vn/thi-truong-chung-khoan.chn",
            "max_depth": 1,
            "max_pages": 50,
            "patterns": [
                r"^https?://(?:www\.)?cafef\.vn/.+?-\d{17,18}\.chn$",
            ],
            "category": "Chứng khoán",
            "target_prompt": "Select investment-critical articles from CafeF's stock market section. Focus on market analysis, macroeconomic trends affecting stocks, corporate earnings reports, M&A activities, and official announcements from listed companies. Prioritize deep analysis over simple price updates. Exclude general business news not directly tied to stock market performance.",
        },
        {
            "url": "https://genk.vn/ai.chn",
            "max_depth": 1,
            "max_pages": 50,
            "patterns": [
                r"^https?://(?:www\.)?genk\.vn/.+?-\d{17,18}\.chn$",
            ],
            "category": "AI & Công nghệ",
            "target_prompt": "From Genk's AI section, curate articles on significant AI advancements, new model releases, in-depth reviews of AI products/tools, and expert analysis of AI trends. Prioritize technical depth and practical application insights. Exclude brief news updates, rumors, and non-AI-related tech news.",
        },
    ]

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

    @property
    def discover_model(self) -> Model:
        google_settings = GoogleModelSettings(
            google_thinking_config={
                "thinking_budget": 4096,
                "include_thoughts": True,
            }
        )
        return GoogleModel(
            model_name=self.llm_model,
            settings=google_settings,
        )


settings = Settings()
