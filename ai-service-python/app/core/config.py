"""
Application Configuration (pydantic-settings)

Reads all configuration from environment variables / .env file.
All settings are typed and validated at startup.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global application settings loaded from .env / environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- Application ----
    ENV: str = Field(default="dev", description="运行环境: dev / test / prod")
    AI_SERVICE_PORT: int = Field(default=8000, description="服务端口")
    CORS_ORIGINS: str = Field(default="*", description="CORS 允许来源（逗号分隔）")
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")

    # ---- MinIO Object Storage ----
    MINIO_ENDPOINT: str = Field(default="localhost:9000", description="MinIO 服务地址")
    MINIO_ACCESS_KEY: str = Field(default="minioadmin", description="MinIO Access Key")
    MINIO_SECRET_KEY: str = Field(default="minioadmin", description="MinIO Secret Key")
    MINIO_BUCKET: str = Field(default="knowledge-rag", description="MinIO Bucket 名称")
    MINIO_SECURE: bool = Field(default=False, description="是否使用 HTTPS")

    # ---- MySQL (via SQLAlchemy or raw connection) ----
    MYSQL_HOST: str = Field(default="localhost", description="MySQL 主机")
    MYSQL_PORT: int = Field(default=3306, description="MySQL 端口")
    MYSQL_USER: str = Field(default="root", description="MySQL 用户名")
    MYSQL_PASSWORD: str = Field(default="", description="MySQL 密码")
    MYSQL_DATABASE: str = Field(default="knowledge_rag", description="MySQL 数据库名")

    # ---- Embedding Model ----
    EMBEDDING_MODEL_NAME: str = Field(
        default="BAAI/bge-large-zh-v1.5",
        description="sentence-transformers 模型名称或 HuggingFace 路径"
    )
    EMBEDDING_DEVICE: str = Field(
        default="cpu",
        description="推理设备: cpu / cuda / cuda:0"
    )
    EMBEDDING_DIMENSION: int = Field(
        default=1024,
        description="Embedding 向量维度"
    )
    EMBEDDING_BATCH_SIZE: int = Field(
        default=32,
        description="批量 embedding 大小"
    )
    EMBEDDING_NORMALIZE: bool = Field(
        default=True,
        description="是否对 embedding 做 L2 归一化"
    )

    # ---- Chroma Vector Store ----
    CHROMA_HOST: str = Field(default="localhost", description="Chroma 服务主机")
    CHROMA_PORT: int = Field(default=8001, description="Chroma 服务端口")
    CHROMA_PERSIST_DIR: str = Field(
        default="./chroma_data",
        description="Chroma 本地持久化目录"
    )
    CHROMA_COLLECTION_PREFIX: str = Field(
        default="kb_",
        description="Chroma Collection 名称前缀（后跟 kb_id）"
    )

    # ---- LLM / Chat ----
    LLM_PROVIDER: str = Field(
        default="deepseek",
        description="LLM 提供商: deepseek / openai / qwen"
    )
    LLM_API_KEY: str = Field(default="", description="LLM API Key")
    LLM_BASE_URL: str = Field(
        default="https://api.deepseek.com/v1",
        description="LLM API Base URL（OpenAI 兼容）"
    )
    LLM_MODEL_NAME: str = Field(
        default="deepseek-chat",
        description="LLM 模型名称"
    )
    LLM_MAX_TOKENS: int = Field(default=2048, description="LLM 最大生成 token 数")
    LLM_TEMPERATURE: float = Field(default=0.7, description="LLM 生成温度")
    LLM_SYSTEM_PROMPT: str = Field(
        default=(
            "你是一个专业的企业知识库问答助手。请严格基于提供的参考文档回答问题。"
            "如果参考文档中没有相关信息，请明确告知用户，不要编造内容。"
            "回答时请引用具体的文档来源。"
        ),
        description="LLM 系统提示词"
    )

    # ---- RAG Parameters ----
    RAG_TOP_K: int = Field(default=5, description="检索返回的 top-k 片段数")
    RAG_SIMILARITY_THRESHOLD: float = Field(
        default=0.35,
        description="相似度阈值（低于此值的结果被过滤）"
    )
    RAG_RERANK_ENABLED: bool = Field(
        default=True,
        description="是否启用 BM25 重排序"
    )
    RAG_HYBRID_ALPHA: float = Field(
        default=0.5,
        description="混合检索权重: 0=纯BM25, 0.5=均等, 1=纯向量"
    )

    # ---- Text Chunking ----
    CHUNK_SIZE: int = Field(default=500, description="文本切片大小（字符数）")
    CHUNK_OVERLAP: int = Field(default=50, description="相邻切片重叠字符数")
    CHUNK_SEPARATORS: str = Field(
        default="\n\n,\n,。,！,？,；,，",
        description="切片分隔符优先级（逗号分隔）"
    )
    CHUNK_MIN_SIZE: int = Field(default=100, description="最小切片大小（低于则合并）")

    # ---- API Timeouts (seconds) ----
    PARSE_TIMEOUT: int = Field(default=300, description="文档解析超时（秒）")
    SEARCH_TIMEOUT: int = Field(default=30, description="搜索超时（秒）")
    CHAT_TIMEOUT: int = Field(default=120, description="对话超时（秒）")

    # ---- Connection Pool ----
    HTTP_POOL_MAX_SIZE: int = Field(default=20, description="HTTP 连接池最大连接数")
    HTTP_POOL_KEEP_ALIVE: int = Field(default=30, description="HTTP Keep-Alive 秒数")

    # ==================== Computed Properties ====================

    @property
    def minio_endpoint_clean(self) -> str:
        """MinIO endpoint without http/https prefix (for minio-py)."""
        return self.MINIO_ENDPOINT.replace("http://", "").replace("https://", "")

    @property
    def chroma_http_url(self) -> str:
        """Full Chroma HTTP server URL."""
        return f"http://{self.CHROMA_HOST}:{self.CHROMA_PORT}"

    @property
    def mysql_dsn(self) -> str:
        """MySQL connection DSN (async)."""
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            f"?charset=utf8mb4"
        )

    @property
    def chunk_separator_list(self) -> list[str]:
        """Parse chunk separators from comma-delimited string."""
        return [
            s.strip()
            for s in self.CHUNK_SEPARATORS.split(",")
            if s.strip()
        ]

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS origins."""
        return [
            o.strip()
            for o in self.CORS_ORIGINS.split(",")
            if o.strip()
        ]

    @property
    def is_dev(self) -> bool:
        """Check if running in development mode."""
        return self.ENV.lower() in ("dev", "development")

    @property
    def is_prod(self) -> bool:
        """Check if running in production mode."""
        return self.ENV.lower() in ("prod", "production")


# ==================== Singleton ====================

@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()


# Module-level instance for easy import
settings = get_settings()
