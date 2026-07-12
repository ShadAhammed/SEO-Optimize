"""Application settings loaded from environment variables via Pydantic."""

from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application configuration.

    All values can be overridden via environment variables or a .env file
    located at the project root.
    """

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── AI Provider Keys ──────────────────────────────────────────────────────
    anthropic_api_key: str = Field(default="", description="Anthropic (Claude) API key")
    deepseek_api_key: str = Field(
        default="",
        description="DeepSeek API key",
        validation_alias=AliasChoices("DEEPSEEK_API_KEY", "DeepSeek_API_KEY", "deepseek_api_key"),
    )
    gemini_api_key: str = Field(
        default="",
        description="Google Gemini API key",
        validation_alias=AliasChoices("GEMINI_API_KEY", "Gemini_API_KEY"),
    )
    # Legacy alias — kept so existing .env files with GOOGLE_API_KEY still work
    google_api_key: str = Field(default="", description="Google (Gemini) API key (legacy)")

    # ── AI Model Config ───────────────────────────────────────────────────────
    claude_model: str = Field(default="claude-sonnet-4-5", description="Claude model name")
    deepseek_model: str = Field(default="deepseek-chat", description="DeepSeek model name")
    gemini_model: str = Field(default="gemini-2.5-flash", description="Gemini model name (legacy)")
    ai_max_retries: int = Field(default=3, ge=1, le=10)
    ai_confidence_threshold: float = Field(default=0.65, ge=0.0, le=1.0)

    # ── Crawl Settings ────────────────────────────────────────────────────────
    crawl_max_pages: int = Field(default=12, ge=1, le=500)
    crawl_max_depth: int = Field(default=2, ge=1, le=10)
    crawl_delay_seconds: float = Field(default=0.5, ge=0.0, le=30.0)
    crawl_user_agent: str = Field(
        default="SEOOptimize/1.0 (+https://seooptimize.local)"
    )

    # ── Rendering Settings ────────────────────────────────────────────────────
    render_viewport_width: int = Field(default=1280, ge=320, le=2560)
    render_mobile_width: int = Field(default=375, ge=320, le=600)
    render_timeout_ms: int = Field(default=20000, ge=5000, le=120000)
    render_wait_until: str = Field(
        default="domcontentloaded",
        description="Playwright wait strategy: domcontentloaded | load | commit",
    )
    render_js_settle_ms: int = Field(
        default=500,
        ge=0,
        le=5000,
        description="Extra ms after page load for JS to render",
    )
    render_full_page_screenshots: bool = Field(
        default=False,
        description="Capture full-page screenshots. Disabled by default for fast viewport-first audits.",
    )

    # ── Quick Audit Settings ─────────────────────────────────────────────────
    quick_audit_enabled: bool = Field(
        default=True,
        description="Prioritize high-value local SEO pages instead of analysing every discovered URL.",
    )
    quick_audit_max_pages: int = Field(default=8, ge=1, le=50)
    quick_audit_ai_pages: int = Field(
        default=3,
        ge=0,
        le=20,
        description="Number of highest-priority pages to send to AI. 0 disables AI calls.",
    )

    # ── Cache Settings ────────────────────────────────────────────────────────
    cache_dir: Path = Field(default=Path("cache"))
    cache_enabled: bool = Field(default=True)

    # ── Application ───────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO")
    app_debug: bool = Field(default=False)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"log_level must be one of {valid}")
        return upper

    @field_validator("render_wait_until")
    @classmethod
    def validate_render_wait_until(cls, v: str) -> str:
        allowed = {"load", "domcontentloaded", "commit"}
        lower = v.lower()
        if lower not in allowed:
            raise ValueError(f"render_wait_until must be one of {allowed}")
        return lower

    @property
    def cache_path(self) -> Path:
        """Resolved absolute cache directory path."""
        return self.cache_dir.resolve()

    @property
    def has_anthropic_key(self) -> bool:
        return bool(self.anthropic_api_key.strip())

    @property
    def has_deepseek_key(self) -> bool:
        return bool(self.deepseek_api_key.strip())

    @property
    def has_gemini_key(self) -> bool:
        """True when a Gemini API key is configured (prefers Gemini_API_KEY over legacy)."""
        return bool(self.gemini_api_key.strip()) or bool(self.google_api_key.strip())

    @property
    def effective_gemini_key(self) -> str:
        """Return the best available Gemini API key."""
        return self.gemini_api_key.strip() or self.google_api_key.strip()

    @property
    def has_google_key(self) -> bool:
        """Legacy: kept for any existing code that checks Gemini availability."""
        return self.has_gemini_key

    @property
    def has_reviewer_key(self) -> bool:
        """True when any reviewer AI (DeepSeek or Gemini) is configured."""
        return self.has_deepseek_key or self.has_gemini_key

    @property
    def reviewer_label(self) -> str:
        """Human-readable name of the active reviewer AI(s)."""
        parts = []
        if self.has_deepseek_key:
            parts.append(f"DeepSeek ({self.deepseek_model})")
        if self.has_gemini_key:
            parts.append(f"Gemini ({self.gemini_model})")
        return " + ".join(parts) if parts else "No reviewer configured"


# Module-level singleton — import and use directly.
settings = Settings()


def reload_settings() -> Settings:
    """Re-read .env and replace the module singleton (Streamlit hot-reload safe)."""
    global settings
    settings = Settings()
    return settings


def has_deepseek_key_for(cfg: Settings | None = None) -> bool:
    """True when a DeepSeek API key is configured (works on stale Settings instances)."""
    s = cfg if cfg is not None else settings
    try:
        return bool(s.has_deepseek_key)
    except AttributeError:
        return bool(getattr(s, "deepseek_api_key", "").strip())


def has_anthropic_key_for(cfg: Settings | None = None) -> bool:
    """True when an Anthropic API key is configured (works on stale Settings instances)."""
    s = cfg if cfg is not None else settings
    try:
        return bool(s.has_anthropic_key)
    except AttributeError:
        return bool(getattr(s, "anthropic_api_key", "").strip())
