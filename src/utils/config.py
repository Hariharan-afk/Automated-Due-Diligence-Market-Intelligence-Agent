"""
Configuration management utility.
Loads configuration from YAML files and environment variables.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Import PathResolver
try:
    from .path_resolver import PathResolver
except ImportError:
    from path_resolver import PathResolver

# Load environment variables from .env file
load_dotenv()


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    calls_per_minute: int = 10
    max_retries: int = 3
    backoff_factor: float = 2.0


@dataclass
class SECFilingConfig:
    """SEC filing configuration."""
    types: list = field(default_factory=lambda: ["10-K", "10-Q"])
    years_to_fetch: int = 3
    sections_to_extract: Dict[str, list] = field(default_factory=lambda: {
        "10-K": ["1", "1A", "7", "8"],
        "10-Q": ["part1item1", "part1item2", "part2item1a"]
    })


@dataclass
class SECAPIConfig:
    """SEC API configuration."""
    api_key: str = ""
    base_url: str = "https://api.sec-api.io"
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    filings: SECFilingConfig = field(default_factory=SECFilingConfig)
    use_free_api: bool = True  # Use free URL-based queries when possible
    cache_enabled: bool = True  # Cache fetched filings


@dataclass
class ChunkingConfig:
    """Document chunking configuration."""
    chunk_size: int = 500  # tokens
    overlap: int = 50  # tokens
    preserve_tables: bool = True
    table_context_paragraphs: int = 2


@dataclass
class VectorStoreConfig:
    """Vector store configuration."""
    type: str = "faiss"  # faiss, pinecone, weaviate
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    index_path: str = "data/vector_store/faiss_index"
    dimension: int = 384  # Dimension for all-MiniLM-L6-v2
    similarity_metric: str = "l2"  # l2, cosine, ip


@dataclass
class AlertConfig:
    """Alerting configuration."""
    enabled: bool = True
    email_enabled: bool = False
    slack_enabled: bool = False
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    sender_email: str = ""
    recipients: list = field(default_factory=list)
    slack_webhook_url: str = ""


@dataclass
class DatabaseConfig:
    """Database configuration."""
    path: str = "data/processed/company_intelligence.db"
    type: str = "sqlite"


@dataclass
class PipelineConfig:
    """Pipeline-wide configuration."""
    sec_filings: SECFilingConfig = field(default_factory=SECFilingConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)


@dataclass
class Config:
    """Main configuration object."""
    # API Keys
    sec_api_key: str = ""
    news_api_key: str = ""

    # Module configs
    sec_api: SECAPIConfig = field(default_factory=SECAPIConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    vector_store: VectorStoreConfig = field(default_factory=VectorStoreConfig)
    alerting: AlertConfig = field(default_factory=AlertConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

    # Paths
    data_dir: Path = field(default_factory=lambda: Path("data"))
    log_dir: Path = field(default_factory=lambda: Path("logs"))
    config_dir: Path = field(default_factory=lambda: Path("config"))

    # Legacy field for backward compatibility
    database_path: str = "data/processed/company_intelligence.db"


class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_path: Path to config.yaml file. Defaults to config/config.yaml
        """
        self.path_resolver = PathResolver()

        if config_path is None:
            config_path = self.path_resolver.get_config_path()
        else:
            config_path = Path(config_path)

        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Config:
        """Load configuration from YAML file and environment variables."""
        config_dict = {}

        # Load from YAML if exists
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f) or {}

        # Override with environment variables
        config = Config()

        # API Keys from environment
        config.sec_api_key = os.getenv("SEC_API_KEY", config_dict.get("sec_api_key", ""))
        config.news_api_key = os.getenv("NEWS_API_KEY", config_dict.get("news_api_key", ""))

        # SEC API configuration
        sec_api_dict = config_dict.get("sec_api", {})
        config.sec_api.api_key = config.sec_api_key
        config.sec_api.base_url = sec_api_dict.get("base_url", config.sec_api.base_url)
        config.sec_api.use_free_api = sec_api_dict.get("use_free_api", True)
        config.sec_api.cache_enabled = sec_api_dict.get("cache_enabled", True)

        # Rate limiting
        rate_limit_dict = sec_api_dict.get("rate_limit", {})
        config.sec_api.rate_limit.calls_per_minute = rate_limit_dict.get(
            "calls_per_minute", 10
        )

        # SEC filings
        filings_dict = sec_api_dict.get("filings", {})
        config.sec_api.filings.types = filings_dict.get("types", ["10-K", "10-Q"])
        config.sec_api.filings.years_to_fetch = filings_dict.get("years_to_fetch", 3)
        config.sec_api.filings.sections_to_extract = filings_dict.get(
            "sections_to_extract",
            config.sec_api.filings.sections_to_extract
        )

        # Pipeline config (for backwards compatibility with existing code)
        pipeline_dict = config_dict.get("pipeline", {})
        sec_filings_dict = pipeline_dict.get("sec_filings", {})
        config.pipeline.sec_filings.years_to_fetch = sec_filings_dict.get(
            "years_to_fetch", 3
        )
        config.pipeline.rate_limit.calls_per_minute = pipeline_dict.get(
            "rate_limit", {}
        ).get("calls_per_minute", 10)

        # Chunking configuration
        chunking_dict = config_dict.get("chunking", {})
        config.chunking.chunk_size = chunking_dict.get("chunk_size", 500)
        config.chunking.overlap = chunking_dict.get("overlap", 50)
        config.chunking.preserve_tables = chunking_dict.get("preserve_tables", True)
        config.chunking.table_context_paragraphs = chunking_dict.get(
            "table_context_paragraphs", 2
        )

        # Vector store configuration
        vector_dict = config_dict.get("vector_store", {})
        config.vector_store.embedding_dim = vector_dict.get("embedding_dim", 768)
        config.vector_store.similarity_metric = vector_dict.get("similarity_metric", "l2")
        config.vector_store.index_type = vector_dict.get("index_type", "faiss")

        # Alerting configuration
        alert_dict = config_dict.get("alerting", {})
        config.alerting.enabled = alert_dict.get("enabled", True)

        email_dict = alert_dict.get("channels", {}).get("email", {})
        config.alerting.email_enabled = email_dict.get("enabled", False)
        config.alerting.smtp_server = email_dict.get("smtp_server", "smtp.gmail.com")
        config.alerting.smtp_port = email_dict.get("smtp_port", 587)
        config.alerting.sender_email = os.getenv(
            "ALERT_EMAIL_SENDER",
            email_dict.get("sender", "")
        )
        config.alerting.recipients = email_dict.get("recipients", [])

        slack_dict = alert_dict.get("channels", {}).get("slack", {})
        config.alerting.slack_enabled = slack_dict.get("enabled", False)
        config.alerting.slack_webhook_url = os.getenv(
            "SLACK_WEBHOOK_URL",
            slack_dict.get("webhook_url", "")
        )

        # Database path
        config.database_path = config_dict.get(
            "database_path",
            "data/processed/company_intelligence.db"
        )

        return config

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.

        Args:
            key: Configuration key (supports dot notation, e.g., 'sec_api.api_key')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = getattr(value, k, None)

            if value is None:
                return default

        return value

    def reload(self):
        """Reload configuration from file."""
        self.config = self._load_config()


# Global configuration instance
_config_manager: Optional[ConfigManager] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """
    Get global configuration instance.

    Args:
        config_path: Path to config file (only used on first call)

    Returns:
        Configuration object
    """
    global _config_manager

    if _config_manager is None:
        _config_manager = ConfigManager(config_path)

    return _config_manager.config


def reload_config():
    """Reload configuration from file."""
    global _config_manager

    if _config_manager is not None:
        _config_manager.reload()
