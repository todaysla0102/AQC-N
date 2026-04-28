from __future__ import annotations

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


load_dotenv()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _to_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _to_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "AQC-N API")
        self.api_prefix = os.getenv("API_PREFIX", "/api")
        self.secret_key = os.getenv("SECRET_KEY", "replace-this-in-production")

        self.database_url_raw = os.getenv("DATABASE_URL", "").strip()
        self.db_host = os.getenv("DB_HOST", "127.0.0.1")
        self.db_port = _to_int("DB_PORT", 3306)
        self.db_name = os.getenv("DB_NAME", "aqc_n")
        self.db_user = os.getenv("DB_USER", "aqc")
        self.db_password = os.getenv("DB_PASSWORD", "replace-this-db-password")
        self.db_pool_size = _to_int("DB_POOL_SIZE", 12)
        self.db_pool_max_overflow = _to_int("DB_POOL_MAX_OVERFLOW", 24)
        self.db_pool_timeout = _to_int("DB_POOL_TIMEOUT", 30)
        self.db_pool_recycle = _to_int("DB_POOL_RECYCLE", 3600)

        self.token_expire_days = _to_int("TOKEN_EXPIRE_DAYS", 30)
        self.token_bytes = _to_int("TOKEN_BYTES", 48)
        self.enable_local_login = _to_bool("ENABLE_LOCAL_LOGIN", False)

        default_cors = "http://localhost:5173,http://127.0.0.1:5173"
        self.cors_origins = _split_csv(os.getenv("CORS_ORIGINS", default_cors))

        self.admin_username = os.getenv("ADMIN_USERNAME", "admin")
        self.admin_email = os.getenv("ADMIN_EMAIL", "admin@aqc.local")
        self.admin_password = os.getenv("ADMIN_PASSWORD", "change-this-password")

        self.symuse_api_base = os.getenv("SYMUSE_API_BASE", "https://account.symuse.com/api").rstrip("/")
        self.symuse_client_id = os.getenv("SYMUSE_CLIENT_ID", "aqc")
        self.symuse_client_secret = os.getenv("SYMUSE_CLIENT_SECRET", "replace-aqc-client-secret")
        self.symuse_auth_page = os.getenv("SYMUSE_AUTH_PAGE", "https://account.symuse.com/auth").strip()
        self.symuse_state_expire_seconds = _to_int("SYMUSE_STATE_EXPIRE_SECONDS", 600)
        self.symuse_state_required = _to_bool("SYMUSE_STATE_REQUIRED", True)
        self.symuse_state_ip_strict = _to_bool("SYMUSE_STATE_IP_STRICT", False)

        self.aqco_sql_path = os.getenv("AQCO_SQL_PATH", "/legacy-data/whaqc_data.sql").strip()
        self.aqco_full_prefix = os.getenv("AQCO_FULL_PREFIX", "aqco_").strip() or "aqco_"
        self.aqco_legacy_bridge_enabled = _to_bool("AQCO_LEGACY_BRIDGE_ENABLED", True)
        self.aqco_legacy_bridge_base = os.getenv("AQCO_LEGACY_BRIDGE_BASE", "https://wx.whaqc.cn/api").strip().rstrip("/")
        self.aqco_legacy_bridge_timeout = _to_int("AQCO_LEGACY_BRIDGE_TIMEOUT", 20)

        self.order_upload_api_url = os.getenv(
            "AQC_ORDER_UPLOAD_API_URL",
            "https://b.kuaidi100.com/v5/open/api/send",
        ).strip()
        self.order_upload_appid = os.getenv("AQC_ORDER_UPLOAD_APPID", "").strip()
        self.order_upload_appsecret = os.getenv("AQC_ORDER_UPLOAD_APPSECRET", "").strip()
        self.order_upload_appuid = os.getenv("AQC_ORDER_UPLOAD_APPUID", "").strip()
        self.order_upload_timeout = _to_int("AQC_ORDER_UPLOAD_TIMEOUT", 20)
        self.order_upload_sender_user_id = _to_int("AQC_ORDER_UPLOAD_SENDER_USER_ID", 1)
        self.order_upload_sender_name = os.getenv("AQC_ORDER_UPLOAD_SENDER_NAME", "").strip()
        self.order_upload_sender_mobile = os.getenv("AQC_ORDER_UPLOAD_SENDER_MOBILE", "").strip()
        self.order_upload_sender_addr = os.getenv("AQC_ORDER_UPLOAD_SENDER_ADDR", "").strip()

        self.symuse_aqc_sync_enabled = _to_bool("SYMUSE_AQC_SYNC_ENABLED", True)
        sync_account_raw = os.getenv("SYMUSE_ADMIN_ACCOUNT", "").strip()
        sync_password_raw = os.getenv("SYMUSE_ADMIN_PASSWORD", "")
        self.symuse_admin_account = sync_account_raw or self.admin_username
        self.symuse_admin_password = sync_password_raw or self.admin_password

    @property
    def database_url(self) -> str:
        if self.database_url_raw:
            return self.database_url_raw

        username = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{username}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )


settings = Settings()
